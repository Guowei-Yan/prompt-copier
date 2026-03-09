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
    params: List[Dict] = None,
    group: str = ''
) -> Prompt:
    """Create a new prompt."""
    prompt = Prompt(
        slug=slug,
        name=name,
        description=description,
        template=template,
        group_name=group,
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
    is_active: bool = None,
    group: str = None
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
    if group is not None:
        prompt.group_name = group
    
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


def clone_prompt(prompt_id: int) -> Optional[Prompt]:
    """Clone a prompt, creating a copy with a unique slug."""
    original = get_prompt_by_id(prompt_id)
    if not original:
        return None

    base_slug = original.slug + '-copy'
    new_slug = base_slug
    counter = 2
    while get_prompt_by_slug(new_slug):
        new_slug = f"{base_slug}-{counter}"
        counter += 1

    return create_prompt(
        slug=new_slug,
        name=f"{original.name} (Copy)",
        template=original.template,
        description=original.description,
        params=original.params,
        group=original.group_name,
    )


def get_all_groups() -> List[str]:
    """Return sorted list of distinct group names."""
    rows = db.session.query(Prompt.group_name).distinct().all()
    groups = sorted([r[0] for r in rows if r[0]])
    return groups


def get_prompt_config() -> Dict[str, Any]:
    """Return prompt configuration for frontend."""
    prompts = get_all_prompts(active_only=True)
    
    result = {}
    for prompt in prompts:
        result[prompt.slug] = {
            'id': prompt.id,
            'name': prompt.name,
            'description': prompt.description,
            'template': prompt.template,
            'params': prompt.params,
            'group': prompt.group_name,
            'has_params': len(prompt.params) > 0
        }
    
    return result
