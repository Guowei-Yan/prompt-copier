import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, Response
from config import AUTH_USERNAME, AUTH_PASSWORD, SECRET_KEY, SQLALCHEMY_DATABASE_URI
from models import db, Prompt
import prompts as prompt_service

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Create tables on startup
with app.app_context():
    db.create_all()


def check_auth(username: str, password: str) -> bool:
    """Check if username/password combination is valid."""
    return username == AUTH_USERNAME and password == AUTH_PASSWORD


def authenticate():
    """Send a 401 response that enables basic auth."""
    return Response(
        'Authentication required',
        401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )


def requires_auth(f):
    """Decorator for routes that require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


# ============ Main Pages ============

@app.route('/')
@requires_auth
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/admin')
@requires_auth
def admin():
    """Serve the admin page."""
    return render_template('admin.html')


# ============ Prompt API ============

@app.route('/api/config')
@requires_auth
def api_config():
    """Return prompt configuration."""
    return jsonify(prompt_service.get_prompt_config())


@app.route('/api/generate', methods=['POST'])
@requires_auth
def api_generate():
    """Generate a prompt with given parameters."""
    data = request.get_json()
    slug = data.get('prompt_id') or data.get('slug')
    params = data.get('params', {})
    
    # Convert string numbers to integers
    for key, value in list(params.items()):
        if isinstance(value, str) and value.lstrip('-').isdigit():
            params[key] = int(value)
    
    try:
        prompt_text = prompt_service.generate_prompt(slug, params)
        return jsonify({'success': True, 'prompt': prompt_text})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ Admin API ============

@app.route('/api/prompts', methods=['GET'])
@requires_auth
def api_list_prompts():
    """List all prompts (including inactive)."""
    prompts = prompt_service.get_all_prompts(active_only=False)
    return jsonify([p.to_dict() for p in prompts])


@app.route('/api/prompts', methods=['POST'])
@requires_auth
def api_create_prompt():
    """Create a new prompt."""
    data = request.get_json()
    
    required = ['slug', 'name', 'template']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
    
    # Check if slug already exists
    if prompt_service.get_prompt_by_slug(data['slug']):
        return jsonify({'success': False, 'error': 'Slug already exists'}), 400
    
    try:
        prompt = prompt_service.create_prompt(
            slug=data['slug'],
            name=data['name'],
            template=data['template'],
            description=data.get('description', ''),
            params=data.get('params', [])
        )
        return jsonify({'success': True, 'prompt': prompt.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/prompts/<int:prompt_id>', methods=['GET'])
@requires_auth
def api_get_prompt(prompt_id):
    """Get a single prompt by ID."""
    prompt = prompt_service.get_prompt_by_id(prompt_id)
    if not prompt:
        return jsonify({'success': False, 'error': 'Prompt not found'}), 404
    return jsonify(prompt.to_dict())


@app.route('/api/prompts/<int:prompt_id>', methods=['PUT'])
@requires_auth
def api_update_prompt(prompt_id):
    """Update a prompt."""
    data = request.get_json()
    
    try:
        prompt = prompt_service.update_prompt(
            prompt_id=prompt_id,
            slug=data.get('slug'),
            name=data.get('name'),
            template=data.get('template'),
            description=data.get('description'),
            params=data.get('params'),
            is_active=data.get('is_active')
        )
        
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt not found'}), 404
        
        return jsonify({'success': True, 'prompt': prompt.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/prompts/<int:prompt_id>', methods=['DELETE'])
@requires_auth
def api_delete_prompt(prompt_id):
    """Delete a prompt."""
    if prompt_service.delete_prompt(prompt_id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Prompt not found'}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
