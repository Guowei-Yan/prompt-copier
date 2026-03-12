"""
Git service — remote repository introspection utilities for the web app.

Provides:
  - get_refs_detailed(url, ssh_key_path?) → {branches: [...], tags: [...]}
  - get_directory_structure(url, ref, pattern, ...) → str
  - get_files_by_pattern(url, ref, pattern, ...) → str
  - get_files_by_paths(url, ref, file_list, ...) → str
"""

import io
import os
import re
import random
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

import git
import requests





_SHA1_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _is_ssh_url(url: str) -> bool:
    return url.startswith("git@") or url.startswith("ssh://")


def _known_hosts_path() -> str:
    home = os.path.expanduser("~")
    dir_path = os.path.join(home, ".git_ssh")
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, "known_hosts")
    if not os.path.exists(file_path):
        try:
            with open(file_path, "a", encoding="utf-8"):
                pass
        except Exception:
            with open(file_path, "a"):
                pass
    return file_path


def _git_ssh_env(
    accept_new: bool = True,
    ssh_key_path: Optional[str] = None,
) -> Dict[str, str]:
    """Build an env dict that configures GIT_SSH_COMMAND.

    If *ssh_key_path* is given the identity file flag is added so git
    uses that specific private key.
    """
    env = os.environ.copy()
    kh = _known_hosts_path()
    mode = "accept-new" if accept_new else "no"
    ssh_cmd = f"ssh -o StrictHostKeyChecking={mode} -o UserKnownHostsFile='{kh}'"
    if ssh_key_path:
        ssh_cmd += f" -i '{ssh_key_path}' -o IdentitiesOnly=yes"
    env["GIT_SSH_COMMAND"] = ssh_cmd
    return env


def _parse_github_url(remote_repo_url: str) -> Optional[Tuple[str, str]]:
    m = re.match(
        r"^(?:[\w.-]+@)?github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        remote_repo_url,
    )
    if m:
        return m.group(1), m.group(2)
    m = re.search(
        r"github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:$|/)", remote_repo_url
    )
    if m:
        return m.group(1), m.group(2)
    return None




def _semver_key_for_sort(tag_name: str) -> Optional[Tuple[int, int, int, Tuple]]:
    m = re.match(
        r"^[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+.*)?$",
        tag_name,
    )
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    prerelease = m.group(4)
    if prerelease is None:
        pre_key: Tuple = (1,)
    else:
        parts = prerelease.split(".")
        conv = []
        for p in parts:
            if p.isdigit():
                conv.append((0, int(p)))
            else:
                conv.append((1, p))
        pre_key = (0,) + tuple(conv)
    return (major, minor, patch, pre_key)


def _tag_sort_key(tag_name: str) -> Tuple:
    k = _semver_key_for_sort(tag_name)
    if k is not None:
        return (0, k)
    return (1, tag_name.lower())




def _run_git_capture(
    repo: git.Repo,
    args: List[str],
    *,
    timeout: int = 300,
    git_global_args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
) -> str:
    cmd = ["git"] + (git_global_args or []) + args

    run_env = env.copy() if env is not None else os.environ.copy()
    run_env["GIT_PAGER"] = "cat"
    run_env["PAGER"] = "cat"

    p = subprocess.run(
        cmd,
        cwd=repo.working_dir,
        env=run_env,
        capture_output=True,
        text=False,
        timeout=timeout,
    )

    stdout = (p.stdout or b"").decode("utf-8", errors="replace").replace("\r\n", "\n")
    stderr = (p.stderr or b"").decode("utf-8", errors="replace").replace("\r\n", "\n")

    if p.returncode != 0:
        raise RuntimeError(
            "Git command failed:\n"
            f"  cwd: {repo.working_dir}\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  rc: {p.returncode}\n"
            f"  stderr: {stderr[:2000]}\n"
            f"  stdout: {stdout[:2000]}\n"
        )

    return stdout


def _run_git_capture_cwd(
    cwd: str,
    args: List[str],
    env: Optional[Dict[str, str]] = None,
    timeout: int = 300,
) -> str:
    cmd = ["git"] + args
    p = subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    if p.returncode != 0:
        raise RuntimeError(
            "Git command failed:\n"
            f"  cwd: {cwd}\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  rc: {p.returncode}\n"
            f"  stderr: {(p.stderr or '').strip()[:4000]}\n"
            f"  stdout: {(p.stdout or '').strip()[:4000]}\n"
        )
    return p.stdout




def _for_each_ref_tags(repo: git.Repo) -> List[Dict]:
    SEP = "<%~%>"
    fmt_fields = [
        "%(refname:short)",
        "%(objectname)",
        "%(objecttype)",
        "%(*objectname)",
        "%(taggername)",
        "%(taggeremail)",
        "%(taggerdate:iso8601)",
        "%(subject)",
        "%(body)",
        "%(*authorname)",
        "%(*authoremail)",
        "%(*committerdate:iso8601)",
        "%(*subject)",
        "%(authorname)",
        "%(authoremail)",
        "%(committerdate:iso8601)",
    ]
    fmt = SEP.join(fmt_fields)

    try:
        out = _run_git_capture(repo, [
            "for-each-ref",
            f"--format={fmt}",
            "--sort=-version:refname",
            "refs/tags/",
        ])
    except RuntimeError as e:
        print(f"Error listing detailed tags: {e}")
        raise

    results: List[Dict] = []
    for line in out.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split(SEP)
        if len(parts) < 16:
            continue

        tag_name = parts[0].strip()
        obj_type = parts[2].strip()
        is_annotated = obj_type == "tag"
        tag_sha = parts[1].strip()
        deref_sha = parts[3].strip()
        commit_sha = deref_sha if deref_sha else tag_sha

        tagger_name = parts[4].strip() or None
        tagger_email = (parts[5].strip().strip("<>")) or None
        tag_date = parts[6].strip() or None
        tag_subject = parts[7].strip()
        tag_body = parts[8].strip()
        tag_message = tag_subject
        if tag_body:
            tag_message = tag_subject + "\n" + tag_body

        if is_annotated:
            commit_author_name = parts[9].strip() or None
            commit_author_email = (parts[10].strip().strip("<>")) or None
            commit_date_val = parts[11].strip() or None
            commit_subject = parts[12].strip() or None
        else:
            commit_author_name = parts[13].strip() or None
            commit_author_email = (parts[14].strip().strip("<>")) or None
            commit_date_val = parts[15].strip() or None
            commit_subject = tag_subject

        results.append({
            "name": tag_name,
            "tag_sha": tag_sha,
            "commit_sha": commit_sha,
            "is_annotated": is_annotated,
            "tagger_name": tagger_name,
            "tagger_email": tagger_email,
            "tag_date": tag_date,
            "tag_message": tag_message if is_annotated else None,
            "commit_author_name": commit_author_name,
            "commit_author_email": commit_author_email,
            "commit_date": commit_date_val,
            "commit_subject": commit_subject,
        })
    return results




def _fetch_remote_archive_bytes(
    remote_repo_url: str,
    branch: str,
    specific_paths: Optional[List[str]] = None,
    ssh_key_path: Optional[str] = None,
) -> Tuple[bytes, bool]:
    is_gzipped = False
    github_details = _parse_github_url(remote_repo_url)
    if github_details:
        if specific_paths:
            print(
                f"Warning: 'specific_paths' argument is ignored when fetching "
                f"from GitHub API for URL: {remote_repo_url}"
            )
        owner, repo_name = github_details
        api_url = (
            f"https://api.github.com/repos/{owner}/{repo_name}/tarball/{branch}"
        )
        print(f"Attempting to fetch archive from GitHub API: {api_url}")
        try:
            headers = {"Accept": "application/vnd.github.v3+json"}
            response = requests.get(
                api_url, headers=headers, stream=True, timeout=60
            )
            response.raise_for_status()
            archive_data = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                archive_data.write(chunk)
            is_gzipped = True
            print(
                f"Successfully fetched archive from GitHub API "
                f"({len(archive_data.getvalue())} bytes)."
            )
            return archive_data.getvalue(), is_gzipped
        except requests.exceptions.RequestException as e:
            print(f"Error fetching archive from GitHub API ({api_url}): {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text[:500]}")
            raise
    else:
        print(
            f"Attempting 'git archive --remote' for non-GitHub URL: "
            f"{remote_repo_url}"
        )
        cmd = ["git", "archive", f"--remote={remote_repo_url}", branch]
        if specific_paths:
            cmd.extend(specific_paths)

        try:
            if _is_ssh_url(remote_repo_url):
                try:
                    process = subprocess.run(
                        cmd,
                        capture_output=True,
                        check=True,
                        env=_git_ssh_env(True, ssh_key_path),
                    )
                except subprocess.CalledProcessError as e1:
                    errtxt = (
                        e1.stderr.decode("utf-8", errors="replace")
                        if isinstance(e1.stderr, (bytes, bytearray))
                        else (e1.stderr or "")
                    )
                    if (
                        "bad configuration" in errtxt.lower()
                        or "unknown option" in errtxt.lower()
                        or "bad configuration value" in errtxt.lower()
                    ):
                        process = subprocess.run(
                            cmd,
                            capture_output=True,
                            check=True,
                            env=_git_ssh_env(False, ssh_key_path),
                        )
                    else:
                        raise
            else:
                process = subprocess.run(
                    cmd, capture_output=True, check=True
                )
            print(
                f"Successfully fetched archive via 'git archive --remote' "
                f"({len(process.stdout)} bytes)."
            )
            return process.stdout, is_gzipped
        except subprocess.CalledProcessError as e:
            error_message = e.stderr.decode("utf-8", errors="replace").strip()
            path_info = (
                f"paths: {specific_paths}" if specific_paths else "entire branch"
            )
            detailed_error_msg = (
                f"Error fetching remote archive from '{remote_repo_url}' "
                f"branch '{branch}' ({path_info}) using 'git archive --remote'.\n"
                f"Git command: '{' '.join(cmd)}'\n"
                f"Return code: {e.returncode}\n"
                f"Stderr: {error_message}"
            )
            print(detailed_error_msg)
            raise
        except FileNotFoundError:
            print(
                "Error: 'git' command not found. "
                "Please ensure Git is installed and in your PATH."
            )
            raise
        except Exception as e_other:
            path_info = (
                f"paths: {specific_paths}" if specific_paths else "entire branch"
            )
            print(
                f"An unexpected error occurred while trying to fetch remote "
                f"archive from '{remote_repo_url}' branch '{branch}' "
                f"({path_info}) using 'git archive --remote': {e_other}"
            )
            raise


def _iterate_tar_members_from_bytes(
    archive_bytes: bytes,
    is_gzipped: bool = False,
) -> Generator[Tuple[tarfile.TarInfo, Optional[bytes]], None, None]:
    mode = "r:gz" if is_gzipped else "r:"
    try:
        with io.BytesIO(archive_bytes) as bio:
            with tarfile.open(fileobj=bio, mode=mode) as tar:
                for member in tar:
                    if member.isfile():
                        file_content_stream = tar.extractfile(member)
                        if file_content_stream:
                            yield member, file_content_stream.read()
                        else:
                            yield member, None
                    else:
                        yield member, None
    except tarfile.TarError as e:
        print(f"Error reading tar archive from byte stream (mode: '{mode}'): {e}")
        if is_gzipped and "not a gzip file" in str(e).lower():
            print("Attempting to read as uncompressed tar...")
            try:
                with io.BytesIO(archive_bytes) as bio_retry:
                    with tarfile.open(fileobj=bio_retry, mode="r:") as tar_retry:
                        for member in tar_retry:
                            if member.isfile():
                                s = tar_retry.extractfile(member)
                                if s:
                                    yield member, s.read()
                                else:
                                    yield member, None
                            else:
                                yield member, None
                        return
            except tarfile.TarError as e_retry:
                print(f"Retry with mode 'r:' also failed: {e_retry}")
                raise e_retry
        raise




def _shallow_clone_for_ref_info(
    remote_url: str,
    *,
    ssh_key_path: Optional[str] = None,
    timeout: int = 300,
) -> Tuple[str, git.Repo]:
    tmp_dir = tempfile.mkdtemp(prefix="git_ref_info_")
    env = (
        _git_ssh_env(True, ssh_key_path)
        if _is_ssh_url(remote_url)
        else None
    )
    cmd = [
        "git",
        "clone",
        "--bare",
        "--filter=tree:0",
        "--no-checkout",
        remote_url,
        tmp_dir,
    ]
    try:
        subprocess.run(
            cmd, capture_output=True, check=True, timeout=timeout, env=env
        )
    except subprocess.CalledProcessError as e1:
        errtxt = (e1.stderr or b"").decode("utf-8", errors="replace")
        if _is_ssh_url(remote_url) and (
            "bad configuration" in errtxt.lower()
            or "unknown option" in errtxt.lower()
        ):
            env2 = _git_ssh_env(False, ssh_key_path)
            subprocess.run(
                cmd, capture_output=True, check=True, timeout=timeout, env=env2
            )
        else:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return tmp_dir, git.Repo(tmp_dir)




def _detect_common_prefix(archive_bytes: bytes, is_gzipped: bool) -> str:
    temp_paths = [
        member.name.replace("\\", "/")
        for member, _ in _iterate_tar_members_from_bytes(archive_bytes, is_gzipped)
    ]
    if temp_paths:
        first_parts = temp_paths[0].split("/")
        if len(first_parts) > 1:
            potential = first_parts[0] + "/"
            if all(p.startswith(potential) for p in temp_paths):
                return potential
    return ""






def get_refs_detailed(
    remote_repo_url: str,
    ssh_key_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Return ``{branches: [...], tags: [...]}`` with detailed ref info."""
    import pandas as pd

    print(f"Cloning (treeless) to get detailed ref info for {remote_repo_url}")
    tmp_dir = None
    try:
        tmp_dir, tmp_repo = _shallow_clone_for_ref_info(
            remote_repo_url, ssh_key_path=ssh_key_path
        )


        SEP = "<%~%>"
        branch_fmt_fields = [
            "%(refname:short)",
            "%(objectname)",
            "%(authorname)",
            "%(authoremail)",
            "%(committerdate:iso8601)",
            "%(subject)",
        ]
        branch_fmt = SEP.join(branch_fmt_fields)
        branch_out = _run_git_capture(tmp_repo, [
            "for-each-ref",
            f"--format={branch_fmt}",
            "--sort=-committerdate",
            "refs/heads/",
        ])

        branch_rows: List[Dict] = []
        for line in branch_out.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split(SEP)
            if len(parts) < 6:
                continue
            branch_rows.append({
                "name": parts[0].strip(),
                "commit_sha": parts[1].strip(),
                "author_name": parts[2].strip(),
                "author_email": parts[3].strip().strip("<>"),
                "commit_date": parts[4].strip(),
                "commit_subject": parts[5].strip(),
            })


        tag_rows = _for_each_ref_tags(tmp_repo)
        tag_rows.sort(key=lambda d: _tag_sort_key(d["name"]))

        print(
            f"Found {len(branch_rows)} branch(es) and {len(tag_rows)} tag(s)."
        )
        return {"branches": branch_rows, "tags": tag_rows}

    except Exception as e:
        print(f"Error getting detailed refs: {e}")
        raise
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def get_directory_structure(
    remote_repo_url: str,
    ref: str,
    pattern: str = r".",
    *,
    exclude_dirs: Optional[List[str]] = None,
    dir_pattern: Optional[str] = None,
    dir_regex_flags: int = 0,
    include_subdirs: bool = False,
    summarize_threshold: int = 20,
    summarize_dominance_ratio: float = 0.8,
    summarize_sample_count: int = 1,
    ssh_key_path: Optional[str] = None,
) -> str:
    """Return directory-structure text for a remote repo / ref."""
    pattern_regex = re.compile(pattern)
    dir_pattern_regex = (
        re.compile(dir_pattern, dir_regex_flags) if dir_pattern else None
    )
    exclude_dirs_set: Set[str] = set(exclude_dirs or [])
    directory_files: Dict[str, List[str]] = {}
    directory_subdirs: Dict[str, set] = {}

    print(
        f"Fetching archive for {remote_repo_url} ref '{ref}' to list structure..."
    )
    archive_bytes, is_gzipped = _fetch_remote_archive_bytes(
        remote_repo_url, ref, specific_paths=None, ssh_key_path=ssh_key_path
    )
    common_prefix_to_strip = _detect_common_prefix(archive_bytes, is_gzipped)
    if common_prefix_to_strip:
        print(f"Detected common prefix: '{common_prefix_to_strip}'")

    for member_info, _ in _iterate_tar_members_from_bytes(
        archive_bytes, is_gzipped
    ):
        original_path = member_info.name.replace("\\", "/")
        file_path = (
            original_path[len(common_prefix_to_strip):]
            if original_path.startswith(common_prefix_to_strip)
            else original_path
        )
        if not file_path:
            continue

        path_parts = file_path.rstrip("/").split("/")
        if any(part in exclude_dirs_set for part in path_parts):
            continue

        if member_info.isfile() and pattern_regex.search(file_path):
            dir_name = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)
            directory_files.setdefault(dir_name, []).append(base_name)

        if include_subdirs:
            for i in range(len(path_parts)):
                if i == len(path_parts) - 1 and member_info.isfile():
                    break
                parent_dir = "/".join(path_parts[:i])
                subdir_name = path_parts[i]
                if subdir_name:
                    directory_subdirs.setdefault(parent_dir, set()).add(
                        subdir_name
                    )

    lines: List[str] = []
    all_dirs = sorted(
        set(directory_files.keys()) | set(directory_subdirs.keys())
    )
    report_dirs = (
        [d for d in all_dirs if dir_pattern_regex.search(d)]
        if dir_pattern_regex
        else all_dirs
    )

    if not report_dirs:
        return (
            f"No files or directories found matching the criteria in ref "
            f"'{ref}' of '{remote_repo_url}'.\n"
        )

    for dir_name_key in report_dirs:
        files_in_dir = sorted(directory_files.get(dir_name_key, []))
        subdirs_in_dir = sorted(directory_subdirs.get(dir_name_key, set()))

        if not files_in_dir and not (include_subdirs and subdirs_in_dir):
            continue

        display = dir_name_key if dir_name_key else "root"
        files_written = False

        if files_in_dir:
            lines.append(f"`{display}` contains files:\n```")
            num_files = len(files_in_dir)
            if num_files > summarize_threshold:
                exts = [os.path.splitext(f)[1].lower() for f in files_in_dir]
                ext_counts: Dict[str, int] = {}
                for e in exts:
                    ext_counts[e] = ext_counts.get(e, 0) + 1
                if ext_counts:
                    most_common = max(ext_counts, key=lambda k: ext_counts[k])
                    most_common_count = ext_counts[most_common]
                    if most_common_count / num_files > summarize_dominance_ratio:
                        for fi in sorted(
                            f
                            for f in files_in_dir
                            if os.path.splitext(f)[1].lower() != most_common
                        ):
                            lines.append(f"  {fi}")
                        dom = [
                            f
                            for f in files_in_dir
                            if os.path.splitext(f)[1].lower() == most_common
                        ]
                        n = max(summarize_sample_count, 1)
                        samples = random.sample(dom, min(n, len(dom)))
                        if most_common in (".jpg", ".jpeg", ".png", ".gif", ".bmp"):
                            desc = "picture"
                        else:
                            desc = most_common[1:] if most_common else "other"
                        lines.append(
                            f"\n... and {most_common_count} {desc} files "
                            f"like {', '.join(samples)}"
                        )
                    else:
                        for fi in files_in_dir:
                            lines.append(f"  {fi}")
                else:
                    for fi in files_in_dir:
                        lines.append(f"  {fi}")
            else:
                for fi in files_in_dir:
                    lines.append(f"  {fi}")
            lines.append("```")
            files_written = True

        if include_subdirs and subdirs_in_dir:
            if files_written:
                lines.append("and contains folders:\n```")
            else:
                lines.append(f"`{display}` contains folders:\n```")
            for sd in subdirs_in_dir:
                lines.append(f"  {sd}/")
            lines.append("```")

        lines.append("")

    return "\n".join(lines)


def get_files_by_pattern(
    remote_repo_url: str,
    ref: str,
    pattern: str,
    *,
    content_regex: Optional[str] = None,
    exclude_dirs: Optional[List[str]] = None,
    dir_pattern: Optional[str] = None,
    dir_regex_flags: int = 0,
    ssh_key_path: Optional[str] = None,
) -> str:
    """Return file contents matching *pattern* as formatted text."""
    pattern_regex = re.compile(pattern)
    content_compiled = re.compile(content_regex) if content_regex else None
    dir_pattern_regex = (
        re.compile(dir_pattern, dir_regex_flags) if dir_pattern else None
    )
    exclude_dirs_set: Set[str] = set(exclude_dirs or [])
    files_written = 0

    print(f"Fetching archive for {remote_repo_url} ref '{ref}' to extract files...")
    archive_bytes, is_gzipped = _fetch_remote_archive_bytes(
        remote_repo_url, ref, specific_paths=None, ssh_key_path=ssh_key_path
    )
    common_prefix = _detect_common_prefix(archive_bytes, is_gzipped)

    chunks: List[str] = []

    for member_info, content_bytes in _iterate_tar_members_from_bytes(
        archive_bytes, is_gzipped
    ):
        if not member_info.isfile() or content_bytes is None:
            continue

        original_path = member_info.name.replace("\\", "/")
        effective = (
            original_path[len(common_prefix):]
            if common_prefix and original_path.startswith(common_prefix)
            else original_path
        )
        if not effective:
            continue

        parts = effective.split("/")
        if any(part in exclude_dirs_set for part in parts):
            continue

        if pattern_regex.search(effective):
            dir_for_match = os.path.dirname(effective)
            if dir_pattern_regex and not dir_pattern_regex.search(dir_for_match):
                continue

            try:
                text = content_bytes.decode("utf-8", errors="replace")
                text = "\n".join(text.splitlines())
                size = len(content_bytes)
                if size > 30720:
                    print(
                        f"Large file from remote: {effective} "
                        f"({size / 1024:.2f}KB)"
                    )

                if content_compiled and not content_compiled.search(text):
                    continue

                chunks.append(f"`{effective}` ->\n```\n{text}\n```\n")
                files_written += 1
            except Exception as e_file:
                print(f"Error processing {effective}: {e_file}")
                chunks.append(
                    f"`{effective}` ->\n```\n"
                    f"[Error processing file: {e_file}. "
                    f"Size: {len(content_bytes)} bytes]\n```\n"
                )

    if files_written == 0:
        return (
            f"No files found matching the specified criteria in ref '{ref}' "
            f"of '{remote_repo_url}'.\n"
        )

    print(f"Matched {files_written} file(s) from remote.")
    return "\n".join(chunks)


def get_files_by_paths(
    remote_repo_url: str,
    ref: str,
    file_list: List[str],
    *,
    exclude_dirs: Optional[List[str]] = None,
    ssh_key_path: Optional[str] = None,
) -> str:
    """Return file contents for an explicit list of paths."""
    files_to_find: Set[str] = set(file_list)
    exclude_dirs_set: Set[str] = set(exclude_dirs or [])
    files_written = 0

    print(
        f"Fetching archive for {remote_repo_url} ref '{ref}' "
        f"to extract specific files..."
    )
    archive_bytes, is_gzipped = _fetch_remote_archive_bytes(
        remote_repo_url, ref, ssh_key_path=ssh_key_path
    )
    common_prefix = _detect_common_prefix(archive_bytes, is_gzipped)

    chunks: List[str] = []

    for member_info, content_bytes in _iterate_tar_members_from_bytes(
        archive_bytes, is_gzipped
    ):
        if not member_info.isfile() or content_bytes is None:
            continue

        original = member_info.name.replace("\\", "/")
        effective = (
            original[len(common_prefix):]
            if common_prefix and original.startswith(common_prefix)
            else original
        )
        if not effective:
            continue

        if effective in files_to_find:
            parts = effective.split("/")
            if any(part in exclude_dirs_set for part in parts):
                continue

            try:
                text = content_bytes.decode("utf-8", errors="replace")
                text = "\n".join(text.splitlines())
                chunks.append(f"`{effective}` ->\n```\n{text}\n```\n")
                files_written += 1
            except Exception as e_file:
                print(f"Error processing {effective}: {e_file}")
                chunks.append(
                    f"`{effective}` ->\n```\n"
                    f"[Error processing file: {e_file}]\n```\n"
                )

    if files_written == 0:
        return (
            f"No matching files from the provided list were found in ref "
            f"'{ref}' of '{remote_repo_url}'.\n"
        )

    print(f"Matched {files_written} file(s) from remote.")
    return "\n".join(chunks)
