from models import db, Prompt
from typing import Dict, Any, List, Optional


def get_all_prompts(active_only: bool = True) -> List[Prompt]:
    """Get all prompts from database."""
    query = Prompt.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Prompt.name).all()


def get_prompt_by_slug(slug: str) -> Optional[Prompt]:
    """Get a prompt by its slug."""
    return Prompt.query.filter_by(slug=slug).first()


def get_prompt_by_id(prompt_id: int) -> Optional[Prompt]:
    """Get a prompt by its ID."""
    return Prompt.query.get(prompt_id)


def create_prompt(
    slug: str,
    name: str,
    template: str,
    description: str = '',
    params: List[Dict] = None
) -> Prompt:
    """Create a new prompt."""
    prompt = Prompt(
        slug=slug,
        name=name,
        description=description,
        template=template,
    )
    prompt.params = params or []
    db.session.add(prompt)
    db.session.commit()
    return prompt


def update_prompt(
    prompt_id: int,
    slug: str = None,
    name: str = None,
    template: str = None,
    description: str = None,
    params: List[Dict] = None,
    is_active: bool = None
) -> Optional[Prompt]:
    """Update an existing prompt."""
    prompt = get_prompt_by_id(prompt_id)
    if not prompt:
        return None
    
    if slug is not None:
        prompt.slug = slug
    if name is not None:
        prompt.name = name
    if template is not None:
        prompt.template = template
    if description is not None:
        prompt.description = description
    if params is not None:
        prompt.params = params
    if is_active is not None:
        prompt.is_active = is_active
    
    db.session.commit()
    return prompt


def delete_prompt(prompt_id: int) -> bool:
    """Delete a prompt."""
    prompt = get_prompt_by_id(prompt_id)
    if not prompt:
        return False
    
    db.session.delete(prompt)
    db.session.commit()
    return True


def generate_prompt(slug: str, params: Dict[str, Any] = None) -> str:
    """Generate a prompt by slug with given parameters."""
    prompt = get_prompt_by_slug(slug)
    if not prompt:
        raise ValueError(f"Prompt not found: {slug}")
    
    return prompt.generate(params)


def get_prompt_config() -> Dict[str, Any]:
    """Return prompt configuration for frontend."""
    prompts = get_all_prompts(active_only=True)
    
    result = {}
    for prompt in prompts:
        result[prompt.slug] = {
            'id': prompt.id,
            'name': prompt.name,
            'description': prompt.description,
            'params': prompt.params,
            'has_params': len(prompt.params) > 0
        }
    
    return result
