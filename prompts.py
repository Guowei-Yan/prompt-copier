from models import db, Prompt, SavedParams
from typing import Dict, Any, List, Optional


def get_all_prompts(active_only: bool = True) -> List[Prompt]:
    query = Prompt.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Prompt.name).all()


def get_prompt_by_slug(slug: str) -> Optional[Prompt]:
    return Prompt.query.filter_by(slug=slug).first()


def get_prompt_by_id(prompt_id: int) -> Optional[Prompt]:
    return Prompt.query.get(prompt_id)


def create_prompt(
    slug: str,
    name: str,
    template: str,
    description: str = '',
    params: List[Dict] = None,
    group: str = '',
    groups: List[str] = None
) -> Prompt:
    prompt = Prompt(
        slug=slug,
        name=name,
        description=description,
        template=template,
    )
    if groups is not None:
        prompt.groups = groups
    else:
        prompt.group_name = group
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
    group: str = None,
    groups: List[str] = None
) -> Optional[Prompt]:
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
    if groups is not None:
        prompt.groups = groups
    elif group is not None:
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
    prompt = get_prompt_by_slug(slug)
    if not prompt:
        raise ValueError(f"Prompt not found: {slug}")
    
    return prompt.generate(params)


def clone_prompt(prompt_id: int) -> Optional[Prompt]:
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
        groups=original.groups,
    )


def get_all_groups() -> List[str]:
    rows = db.session.query(Prompt.group_name).all()
    groups_set = set()
    for r in rows:
        if r[0]:
            for g in r[0].split(','):
                g = g.strip()
                if g:
                    groups_set.add(g)
    return sorted(groups_set)


def get_prompt_config() -> Dict[str, Any]:
    prompts = get_all_prompts(active_only=True)
    
    result = {}
    for prompt in prompts:
        result[prompt.slug] = {
            'id': prompt.id,
            'name': prompt.name,
            'description': prompt.description,
            'template': prompt.template,
            'params': prompt.params,
            'group': prompt.groups[0] if prompt.groups else '',
            'groups': prompt.groups,
            'has_params': len(prompt.params) > 0
        }
    
    return result


def get_all_saved_params() -> Dict[str, Dict[str, str]]:
    rows = SavedParams.query.all()
    result = {}
    for r in rows:
        key = r.group_key
        if key not in result:
            result[key] = {}
        result[key][f"{r.slug}.{r.param_name}"] = r.param_value
    return result


def save_params(group_key: str, values: Dict[str, str]) -> None:
    for composite_key, value in values.items():
        parts = composite_key.split('.', 1)
        if len(parts) != 2:
            continue
        slug, param_name = parts

        existing = SavedParams.query.filter_by(
            group_key=group_key,
            slug=slug,
            param_name=param_name,
        ).first()

        if existing:
            existing.param_value = value
        else:
            row = SavedParams(
                group_key=group_key,
                slug=slug,
                param_name=param_name,
                param_value=value,
            )
            db.session.add(row)

    db.session.commit()


def delete_saved_params(group_key: str, slug: str) -> bool:
    rows = SavedParams.query.filter_by(group_key=group_key, slug=slug).all()
    if not rows:
        return False
    for r in rows:
        db.session.delete(r)
    db.session.commit()
    return True
