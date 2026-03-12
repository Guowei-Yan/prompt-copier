import os
from datetime import timedelta
from functools import wraps
import traceback
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from config import AUTH_USERNAME, AUTH_PASSWORD, SECRET_KEY, SQLALCHEMY_DATABASE_URI
from models import db, Prompt
import prompts as prompt_service
import git_service
import ssh_keys

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

db.init_app(app)

with app.app_context():
    db.create_all()
    # Migrate: add group_name column if it doesn't exist (for existing DBs)
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('prompts')]
    if 'group_name' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE prompts ADD COLUMN group_name VARCHAR(100) DEFAULT '' NOT NULL"))
            conn.commit()


def check_auth(username: str, password: str) -> bool:
    return username == AUTH_USERNAME and password == AUTH_PASSWORD


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


# ---------------------------------------------------------------------------
# Git Explorer
# ---------------------------------------------------------------------------

@app.route('/git')
@requires_auth
def git_explorer():
    return render_template('git_explorer.html')


# ---- SSH Key Management ----

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


# ---- Git Operations ----

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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
