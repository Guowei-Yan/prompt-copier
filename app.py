import os
from datetime import timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from config import AUTH_USERNAME, AUTH_PASSWORD, SECRET_KEY, SQLALCHEMY_DATABASE_URI
from models import db, Prompt
import prompts as prompt_service

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
            group=data.get('group', '')
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
            group=data.get('group')
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


@app.route('/api/groups')
@requires_auth
def api_groups():
    return jsonify(prompt_service.get_all_groups())


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
