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
    params_json = db.Column(db.Text, default='[]')
    group_name = db.Column(db.String(100), default='', nullable=False)
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

    @property
    def groups(self):
        if not self.group_name:
            return []
        return [g.strip() for g in self.group_name.split(',') if g.strip()]

    @groups.setter
    def groups(self, value):
        if value:
            self.group_name = ','.join(g.strip() for g in value if g.strip())
        else:
            self.group_name = ''

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
            'group': self.groups[0] if self.groups else '',
            'groups': self.groups,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SavedParams(db.Model):
    __tablename__ = 'saved_params'

    id = db.Column(db.Integer, primary_key=True)
    group_key = db.Column(db.String(500), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    param_name = db.Column(db.String(100), nullable=False)
    param_value = db.Column(db.Text, default='')

    __table_args__ = (
        db.UniqueConstraint('group_key', 'slug', 'param_name', name='uq_saved_params'),
    )

    def to_dict(self):
        return {
            'group_key': self.group_key,
            'slug': self.slug,
            'param_name': self.param_name,
            'param_value': self.param_value,
        }


class AppSettings(db.Model):
    __tablename__ = 'app_settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, default='')

    @staticmethod
    def get(key, default=''):
        row = AppSettings.query.get(key)
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = AppSettings.query.get(key)
        if row:
            row.value = value
        else:
            row = AppSettings(key=key, value=value)
            db.session.add(row)
        db.session.commit()


class SavedRepo(db.Model):
    __tablename__ = 'saved_repos'

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False, unique=True)
    label = db.Column(db.String(200), default='')
    ssh_key_label = db.Column(db.String(100), default='')
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'label': self.label,
            'ssh_key_label': self.ssh_key_label,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
