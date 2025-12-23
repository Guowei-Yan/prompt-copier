from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class Prompt(db.Model):
    __tablename__ = 'prompts'
    
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    template = db.Column(db.Text, nullable=False)
    params_json = db.Column(db.Text, default='[]')  # JSON array of param configs
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def params(self):
        try:
            return json.loads(self.params_json) if self.params_json else []
        except:
            return []
    
    @params.setter
    def params(self, value):
        self.params_json = json.dumps(value) if value else '[]'
    
    def generate(self, param_values: dict = None) -> str:
        result = self.template
        
        if param_values:
            for key, value in param_values.items():
                result = result.replace('{' + key + '}', str(value))
        
        for param in self.params:
            placeholder = '{' + param['name'] + '}'
            if placeholder in result:
                result = result.replace(placeholder, str(param.get('default', '')))
        
        return result
    
    def to_dict(self):
        """Convert to dictionary for API response."""
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'template': self.template,
            'params': self.params,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
