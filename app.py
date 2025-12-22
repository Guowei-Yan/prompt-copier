from functools import wraps
from flask import Flask, request, jsonify, render_template, Response
from config import AUTH_USERNAME, AUTH_PASSWORD, SECRET_KEY
from prompts import get_prompt_config, generate_prompt

app = Flask(__name__)
app.secret_key = SECRET_KEY


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


@app.route('/')
@requires_auth
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/config')
@requires_auth
def api_config():
    """Return prompt configuration."""
    return jsonify(get_prompt_config())


@app.route('/api/generate', methods=['POST'])
@requires_auth
def api_generate():
    """Generate a prompt with given parameters."""
    data = request.get_json()
    prompt_id = data.get('prompt_id')
    params = data.get('params', {})
    
    # Convert string numbers to integers
    for key, value in params.items():
        if isinstance(value, str) and value.isdigit():
            params[key] = int(value)
        elif isinstance(value, (int, float)):
            params[key] = int(value)
    
    try:
        prompt = generate_prompt(prompt_id, params)
        return jsonify({'success': True, 'prompt': prompt})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
