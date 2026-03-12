import os
from datetime import datetime, timedelta
from functools import wraps
import traceback
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from config import AUTH_USERNAME, AUTH_PASSWORD, SECRET_KEY, SQLALCHEMY_DATABASE_URI
from models import db, Prompt, AppSettings, SavedRepo
import prompts as prompt_service
import git_service
import ssh_keys
import email_service

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

db.init_app(app)

reset_serializer = URLSafeTimedSerializer(SECRET_KEY)

with app.app_context():
    db.create_all()

    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('prompts')]
    if 'group_name' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE prompts ADD COLUMN group_name VARCHAR(100) DEFAULT '' NOT NULL"))
            conn.commit()


    if not AppSettings.get('auth_username'):
        AppSettings.set('auth_username', AUTH_USERNAME)
        AppSettings.set('auth_password', generate_password_hash(AUTH_PASSWORD))


def check_auth(username: str, password: str) -> bool:
    stored_user = AppSettings.get('auth_username', '')
    stored_hash = AppSettings.get('auth_password', '')
    if not stored_user or not stored_hash:
        return False
    return username == stored_user and check_password_hash(stored_hash, password)


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login')
def login():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')

    if check_auth(username, password):
        session.permanent = True
        session['authenticated'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Invalid username or password'}), 401


@app.route('/api/logout')
def api_logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@requires_auth
def index():
    return render_template('index.html')


@app.route('/admin')
@requires_auth
def admin():
    return render_template('admin.html')


@app.route('/settings')
@requires_auth
def settings_page():
    return render_template('settings.html')


@app.route('/api/settings', methods=['GET'])
@requires_auth
def api_get_settings():
    return jsonify({
        'username': AppSettings.get('auth_username', ''),
        'smtp_host': AppSettings.get('smtp_host', ''),
        'smtp_port': AppSettings.get('smtp_port', '587'),
        'smtp_user': AppSettings.get('smtp_user', ''),
        'reset_email': AppSettings.get('reset_email', ''),
        'smtp_configured': email_service.is_smtp_configured(),
    })


@app.route('/api/settings/smtp', methods=['POST'])
@requires_auth
def api_save_smtp():
    data = request.get_json()
    for key in ('smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'reset_email'):
        if key in data:
            AppSettings.set(key, str(data[key]).strip())
    return jsonify({'success': True})


@app.route('/api/test-smtp', methods=['POST'])
@requires_auth
def api_test_smtp():
    try:
        email_service.send_test_email()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/change-credentials', methods=['POST'])
@requires_auth
def api_change_credentials():
    if not email_service.is_smtp_configured():
        return jsonify({'success': False, 'error': 'SMTP must be configured before changing credentials'}), 400

    data = request.get_json()
    current_password = data.get('current_password', '')
    new_username = data.get('new_username', '').strip()
    new_password = data.get('new_password', '')

    if not current_password or not new_username or not new_password:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400

    stored_hash = AppSettings.get('auth_password', '')
    if not check_password_hash(stored_hash, current_password):
        return jsonify({'success': False, 'error': 'Current password is incorrect'}), 403

    AppSettings.set('auth_username', new_username)
    AppSettings.set('auth_password', generate_password_hash(new_password))
    session.clear()
    return jsonify({'success': True})


@app.route('/api/forgot-credentials', methods=['POST'])
def api_forgot_credentials():
    if not email_service.is_smtp_configured():
        return jsonify({'success': False, 'error': 'Password reset is not available — SMTP is not configured'}), 400

    try:
        token = reset_serializer.dumps('reset-credentials', salt='credential-reset')
        reset_url = request.host_url.rstrip('/') + '/reset/' + token
        email_service.send_reset_email(reset_url)
        return jsonify({'success': True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reset/<token>')
def reset_page(token):
    try:
        reset_serializer.loads(token, salt='credential-reset', max_age=3600)
    except (SignatureExpired, BadSignature):
        return render_template('reset.html', error='This reset link is invalid or has expired.')
    return render_template('reset.html', token=token, error=None)


@app.route('/api/reset-credentials', methods=['POST'])
def api_reset_credentials():
    data = request.get_json()
    token = data.get('token', '')
    new_username = data.get('new_username', '').strip()
    new_password = data.get('new_password', '')

    if not token or not new_username or not new_password:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400

    try:
        reset_serializer.loads(token, salt='credential-reset', max_age=3600)
    except SignatureExpired:
        return jsonify({'success': False, 'error': 'This reset link has expired'}), 400
    except BadSignature:
        return jsonify({'success': False, 'error': 'Invalid reset token'}), 400

    AppSettings.set('auth_username', new_username)
    AppSettings.set('auth_password', generate_password_hash(new_password))
    return jsonify({'success': True})



@app.route('/api/config')
@requires_auth
def api_config():
    return jsonify(prompt_service.get_prompt_config())

@app.route('/api/generate', methods=['POST'])
@requires_auth
def api_generate():
    data = request.get_json()
    slug = data.get('prompt_id') or data.get('slug')
    params = data.get('params', {})

    try:
        prompt_text = prompt_service.generate_prompt(slug, params)
        return jsonify({'success': True, 'prompt': prompt_text})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/prompts', methods=['GET'])
@requires_auth
def api_list_prompts():
    prompts = prompt_service.get_all_prompts(active_only=False)
    return jsonify([p.to_dict() for p in prompts])


@app.route('/api/prompts', methods=['POST'])
@requires_auth
def api_create_prompt():
    data = request.get_json()

    required = ['slug', 'name', 'template']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

    if prompt_service.get_prompt_by_slug(data['slug']):
        return jsonify({'success': False, 'error': 'Slug already exists'}), 400

    try:
        prompt = prompt_service.create_prompt(
            slug=data['slug'],
            name=data['name'],
            template=data['template'],
            description=data.get('description', ''),
            params=data.get('params', []),
            group=data.get('group', ''),
            groups=data.get('groups')
        )
        return jsonify({'success': True, 'prompt': prompt.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/prompts/<int:prompt_id>', methods=['GET'])
@requires_auth
def api_get_prompt(prompt_id):
    prompt = prompt_service.get_prompt_by_id(prompt_id)
    if not prompt:
        return jsonify({'success': False, 'error': 'Prompt not found'}), 404
    return jsonify(prompt.to_dict())


@app.route('/api/prompts/<int:prompt_id>', methods=['PUT'])
@requires_auth
def api_update_prompt(prompt_id):
    data = request.get_json()

    try:
        prompt = prompt_service.update_prompt(
            prompt_id=prompt_id,
            slug=data.get('slug'),
            name=data.get('name'),
            template=data.get('template'),
            description=data.get('description'),
            params=data.get('params'),
            is_active=data.get('is_active'),
            group=data.get('group'),
            groups=data.get('groups')
        )

        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt not found'}), 404

        return jsonify({'success': True, 'prompt': prompt.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/prompts/<int:prompt_id>', methods=['DELETE'])
@requires_auth
def api_delete_prompt(prompt_id):
    if prompt_service.delete_prompt(prompt_id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Prompt not found'}), 404


@app.route('/api/prompts/<int:prompt_id>/clone', methods=['POST'])
@requires_auth
def api_clone_prompt(prompt_id):
    prompt = prompt_service.clone_prompt(prompt_id)
    if not prompt:
        return jsonify({'success': False, 'error': 'Prompt not found'}), 404
    return jsonify({'success': True, 'prompt': prompt.to_dict()})


@app.route('/api/saved-params', methods=['GET'])
@requires_auth
def api_get_saved_params():
    return jsonify(prompt_service.get_all_saved_params())


@app.route('/api/saved-params', methods=['POST'])
@requires_auth
def api_save_params():
    data = request.get_json()
    group_key = data.get('group_key', '__all__')
    values = data.get('values', {})

    try:
        prompt_service.save_params(group_key, values)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/saved-params', methods=['DELETE'])
@requires_auth
def api_delete_saved_params():
    group_key = request.args.get('group_key', '__all__')
    slug = request.args.get('slug', '')

    if not slug:
        return jsonify({'success': False, 'error': 'Missing slug parameter'}), 400

    prompt_service.delete_saved_params(group_key, slug)
    return jsonify({'success': True})


@app.route('/api/groups')
@requires_auth
def api_groups():
    return jsonify(prompt_service.get_all_groups())

@app.route('/git')
@requires_auth
def git_explorer():
    return render_template('git_explorer.html')

@app.route('/api/git/ssh-keys', methods=['GET'])
@requires_auth
def api_list_ssh_keys():
    return jsonify(ssh_keys.list_keys())


@app.route('/api/git/ssh-keys', methods=['POST'])
@requires_auth
def api_upload_ssh_key():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    f = request.files['file']
    label = request.form.get('label', '').strip()
    if not label:
        return jsonify({'success': False, 'error': 'Label is required'}), 400
    try:
        path = ssh_keys.save_key(label, f.read())
        return jsonify({'success': True, 'path': path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/git/ssh-keys/<label>', methods=['DELETE'])
@requires_auth
def api_delete_ssh_key(label):
    if ssh_keys.delete_key(label):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Key not found'}), 404

def _resolve_ssh_key(data: dict):
    """Return ssh_key_path from request data or None."""
    label = data.get('ssh_key_label', '').strip()
    if label:
        path = ssh_keys.get_key_path(label)
        if not path:
            raise ValueError(f"SSH key '{label}' not found")
        return path
    return None


@app.route('/api/git/refs', methods=['POST'])
@requires_auth
def api_git_refs():
    data = request.get_json()
    url = (data.get('url') or '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400
    try:
        key_path = _resolve_ssh_key(data)
        result = git_service.get_refs_detailed(url, ssh_key_path=key_path)
        return jsonify({'success': True, **result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/git/structure', methods=['POST'])
@requires_auth
def api_git_structure():
    data = request.get_json()
    url = (data.get('url') or '').strip()
    ref = (data.get('ref') or '').strip()
    pattern = data.get('pattern', r'.')
    if not url or not ref:
        return jsonify({'success': False, 'error': 'URL and ref are required'}), 400
    try:
        key_path = _resolve_ssh_key(data)
        result = git_service.get_directory_structure(
            url, ref, pattern,
            exclude_dirs=data.get('exclude_dirs'),
            dir_pattern=data.get('dir_pattern'),
            include_subdirs=data.get('include_subdirs', False),
            ssh_key_path=key_path,
        )
        return jsonify({'success': True, 'output': result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/git/files', methods=['POST'])
@requires_auth
def api_git_files():
    data = request.get_json()
    url = (data.get('url') or '').strip()
    ref = (data.get('ref') or '').strip()
    pattern = data.get('pattern', r'.')
    if not url or not ref:
        return jsonify({'success': False, 'error': 'URL and ref are required'}), 400
    try:
        key_path = _resolve_ssh_key(data)
        result = git_service.get_files_by_pattern(
            url, ref, pattern,
            content_regex=data.get('content_regex'),
            exclude_dirs=data.get('exclude_dirs'),
            dir_pattern=data.get('dir_pattern'),
            ssh_key_path=key_path,
        )
        return jsonify({'success': True, 'output': result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/git/files-by-path', methods=['POST'])
@requires_auth
def api_git_files_by_path():
    data = request.get_json()
    url = (data.get('url') or '').strip()
    ref = (data.get('ref') or '').strip()
    file_list = data.get('file_list', [])
    if not url or not ref:
        return jsonify({'success': False, 'error': 'URL and ref are required'}), 400
    if not file_list:
        return jsonify({'success': False, 'error': 'file_list is required'}), 400
    try:
        key_path = _resolve_ssh_key(data)
        result = git_service.get_files_by_paths(
            url, ref, file_list,
            exclude_dirs=data.get('exclude_dirs'),
            ssh_key_path=key_path,
        )
        return jsonify({'success': True, 'output': result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/git/repos', methods=['GET'])
@requires_auth
def api_list_saved_repos():
    repos = SavedRepo.query.order_by(SavedRepo.last_used_at.desc()).all()
    return jsonify([r.to_dict() for r in repos])


@app.route('/api/git/repos', methods=['POST'])
@requires_auth
def api_save_repo():
    data = request.get_json()
    url = (data.get('url') or '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400

    repo = SavedRepo.query.filter_by(url=url).first()
    if repo:
        repo.ssh_key_label = data.get('ssh_key_label', repo.ssh_key_label)
        if data.get('label'):
            repo.label = data['label']
        repo.last_used_at = datetime.utcnow()
    else:
        repo = SavedRepo(
            url=url,
            label=data.get('label', ''),
            ssh_key_label=data.get('ssh_key_label', ''),
        )
        db.session.add(repo)
    db.session.commit()
    return jsonify({'success': True, 'repo': repo.to_dict()})


@app.route('/api/git/repos/<int:repo_id>', methods=['DELETE'])
@requires_auth
def api_delete_saved_repo(repo_id):
    repo = SavedRepo.query.get(repo_id)
    if not repo:
        return jsonify({'success': False, 'error': 'Repo not found'}), 404
    db.session.delete(repo)
    db.session.commit()
    return jsonify({'success': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
