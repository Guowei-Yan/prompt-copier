"""Quick verification of multi-group model changes."""
from models import Prompt

# Test groups property
p = Prompt()

# Test setting groups list
p.groups = ['coding', 'writing']
assert p.group_name == 'coding,writing', f"Expected 'coding,writing', got '{p.group_name}'"
assert p.groups == ['coding', 'writing'], f"Expected ['coding', 'writing'], got {p.groups}"

# Test to_dict
d = p.to_dict()
assert d['groups'] == ['coding', 'writing'], f"Expected ['coding', 'writing'], got {d['groups']}"
assert d['group'] == 'coding', f"Expected 'coding', got {d['group']}"

# Test empty groups
p.groups = []
assert p.group_name == '', f"Expected '', got '{p.group_name}'"
assert p.groups == [], f"Expected [], got {p.groups}"

# Test single group backward compat
p.group_name = 'marketing'
assert p.groups == ['marketing'], f"Expected ['marketing'], got {p.groups}"

# Test existing comma-separated data (migration scenario)
p.group_name = 'coding, writing, testing'
assert p.groups == ['coding', 'writing', 'testing'], f"Expected ['coding', 'writing', 'testing'], got {p.groups}"

print("All group model tests passed!")
