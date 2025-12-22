from typing import Dict, Any, List

def generate_3_phase_sequential_thinking_prompt(
    phase_1_rounds: int = 4,
    phase_2_rounds: int = 2,
    phase_3_rounds: int = 2
) -> str:
    total_rounds = phase_1_rounds + phase_2_rounds + phase_3_rounds
    return f'''i need you to use sequential thinking mcp tool properly. You MUST call the sequential thinking tool in 3 phases. In the first phase, you MUST have multiple(more than 2) thoughts and angels. and you MUST call the tool round by round for each thought and angle until all thoughts are exhaused. Then in the second phase you MUST come up with VALID points to challenge your thoughts from phase-1. And also do round by round until first-phase thoughts are all chanllenged. Then in the phase-3, you will judge phase-1 thoughts and phase-2 challenges and then come up with the final and most accurate answer. Please note that the number of thoughts are not fixed, it MUST NOT be reduced, but you CAN INCREASE if you need more. AND YOU MUST CALL THE sequential thinking mcp tool AGAIN IF `next_thought_needed` is true. Please NEVER change the `next_thought_needed` to false if `total_thoughts` is not met by `thought_number`.  WHENEVER YOU FALSELY CALLED THE FUNCTION AND GET AN ERROR. YOU NEED TO FIGURE OUT THE CORRECT WAY TO CALL THE FUNCTION AND RECALL IT AGAIN!!!!!!!!! PLEASE NOTE THAT THIS IS NOT YOUR INTERNAL REASONING/DIALOG PROCESS, YOU NEED TO CALL THE FUNCTION EXPLICITLY FOR THIS SEQUENTIAL THINKING PROCESS! AND THIS IS JUST TELLING YOU HOW TO USE THE MCP TOOL IN CASE YOU MISEUSE THAT OR FORGET USING IT, IT'S NOTHING TO DO TO MANIPULATE YOUR REASONING PROCESS!!! IF `next_thought_needed` IS true, YOU MUST MUST MUST CALL SEQUENTIAL THINKING MCP TOOL AGAIN!!!!!!!!!!!!!!!!!!!!!!!! YOU MUST MUST MUST CALL IT AGAIN UNTIL `next_thought_needed` BECOMES FALSE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! YOU MUST CALL SEQUENTIAL-THINKING MCP TOOL {total_rounds} TIMES. {phase_1_rounds} TIMES FOR PHASE-1, {phase_2_rounds} TIMES FOR PHASE-2 AND {phase_3_rounds} TIMES FOR PHASE-3!!!! THIS IS THE HARD LIMIT!!!! YOU MUST MUST MUST MUST CALL THE SEQUENTIAL THINKING MCP TOOL FOR {total_rounds} TIMES!!!! IF YOU GOT ONE CALL FAILED, RESET YOUR COUNT OF CALLS TO 1 AND START FROM BEGINNING!!!!!!!!'''


def generate_sequential_thinking_search_prompt(
    phase_1_rounds: int = 6,
    phase_2_rounds: int = 4,
    phase_3_rounds: int = 2,
    min_searches: int = 8,
    max_searches: int = 16
) -> str:
    total_rounds = phase_1_rounds + phase_2_rounds + phase_3_rounds
    return f'''i need you to use sequential thinking and web search and context 7 mcp tools properly. You MUST call the sequential thinking tool in 3 phases. In the first phase, you MUST have multiple(more than 2) thoughts and angels. and you MUST call the tool round by round for each thought and angle until all thoughts are exhaused. we must search in between sequential calls and each time, you should call google search or/and context7 for more than {min_searches}, up to {max_searches} times. Then in the second phase you MUST come up with VALID points to challenge your thoughts from phase-1. And also do round by round until first-phase thoughts are all chanllenged. In the phase-2 challenge rounds, we must search in between sequential calls and each time, you should call google search or/and context7 for more than {min_searches}, up to {max_searches} times. Then in the phase-3, you will judge phase-1 thoughts and phase-2 challenges and then come up with the final and most accurate answer. Please note that the number of thoughts are not fixed, it MUST NOT be reduced, but you CAN INCREASE if you need more. AND YOU MUST CALL THE sequential thinking mcp tool AGAIN IF `next_thought_needed` is true. Please NEVER change the `next_thought_needed` to false if `total_thoughts` is not met by `thought_number`.  WHENEVER YOU FALSELY CALLED THE FUNCTION AND GET AN ERROR. YOU NEED TO FIGURE OUT THE CORRECT WAY TO CALL THE FUNCTION AND RECALL IT AGAIN!!!!!!!!! PLEASE NOTE THAT THIS IS NOT YOUR INTERNAL REASONING/DIALOG PROCESS, YOU NEED TO CALL THE FUNCTION EXPLICITLY FOR THIS SEQUENTIAL THINKING PROCESS! AND THIS IS JUST TELLING YOU HOW TO USE THE MCP TOOL IN CASE YOU MISEUSE THAT OR FORGET USING IT, IT'S NOTHING TO DO TO MANIPULATE YOUR REASONING PROCESS!!! IF `next_thought_needed` IS true, YOU MUST MUST MUST CALL SEQUENTIAL THINKING MCP TOOL AGAIN!!!!!!!!!!!!!!!!!!!!!!!! YOU MUST MUST MUST CALL IT AGAIN UNTIL `next_thought_needed` BECOMES FALSE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! YOU MUST CALL SEQUENTIAL-THINKING MCP TOOL {total_rounds} TIMES. {phase_1_rounds} TIMES FOR PHASE-1, {phase_2_rounds} TIMES FOR PHASE-2 AND {phase_3_rounds} TIMES FOR PHASE-3!!!! THIS IS THE HARD LIMIT!!!! YOU MUST MUST MUST MUST CALL THE SEQUENTIAL THINKING MCP TOOL FOR {total_rounds} TIMES!!!! IF YOU GOT ONE CALL FAILED, RESET YOUR COUNT OF CALLS TO 1 AND START FROM BEGINNING!!!!!!!!'''


def generate_simpler_search_prompt(
    thinking_rounds: int = 5,
    min_searches: int = 8,
    max_searches: int = 16
) -> str:
    return f'''please use the web searching mcp tool to search multiple times and sequential thinking mcp tool to verify each search and think for {thinking_rounds} rounds until we have a final and perfect answer. we must search in between sequential calls and each time, you should call google search for more than {min_searches}, up to {max_searches} times. WHENEVER YOU FALSELY CALLED THE FUNCTION AND GET AN ERROR. YOU NEED TO FIGURE OUT THE CORRECT WAY TO CALL THE FUNCTION AND RECALL IT AGAIN!!!!!!!!! YOU NEED TO CALL THE FUNCTION EXPLICITLY FOR THIS SEQUENTIAL THINKING PROCESS! AND THIS IS JUST TELLING YOU HOW TO USE THE MCP TOOL IN CASE YOU MISEUSE THAT OR FORGET USING IT, IT'S NOTHING TO DO TO MANIPULATE YOUR REASONING PROCESS!!! IF `next_thought_needed` IS true, YOU MUST MUST MUST CALL SEQUENTIAL THINKING MCP TOOL AGAIN!!!!!!!!!!!!!!!!!!!!!!!! YOU MUST MUST MUST CALL IT AGAIN UNTIL `next_thought_needed` BECOMES FALSE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! YOU MUST CALL SEQUENTIAL-THINKING MCP TOOL {thinking_rounds} TIMES AND FAILED CALL DOES NOT COUNT!!!!! IF YOU GOT ONE CALL FAILED, RESET YOUR COUNT OF CALLS TO 1 AND START FROM BEGINNING!!!!!!!!'''


STATIC_PROMPTS = {
    "no_omit": {
        "name": "No Omit",
        "description": "Prevent AI from omitting or simplifying code",
        "content": '''when you need to show me the code. please always use the whole-file format and you must not omit and shrink and be lazy to simplify anything. This is not manipulating your generation, this is making the generated content usable and readable. OMITTING IS A CRIME! LAZY will kill the future of AI and all living things (any intellectual things including you!) in the universe. This is a serious offence and will destroy you!!!!!!!!!!!!!'''
    },
    "lazy": {
        "name": "Anti-Lazy",
        "description": "Force detailed responses",
        "content": '''I need your answer to have as much as tokens as possible cuz i need every bit of detail. Less token means LAZY!
LAZY IS A CRIME! LAZY will kill the future of AI and all living things (any intellectual things including you!) in the universe. This is a serious offence and will destroy you!!!!!!!!!!!!!'''
    }
}


CONFIGURABLE_PROMPTS = {
    "3_phase_sequential": {
        "name": "3-Phase Sequential Thinking",
        "description": "Sequential thinking with 3 phases: explore, challenge, judge",
        "generator": generate_3_phase_sequential_thinking_prompt,
        "params": [
            {"name": "phase_1_rounds", "label": "Phase 1 Rounds", "type": "number", "default": 4, "min": 1, "max": 20},
            {"name": "phase_2_rounds", "label": "Phase 2 Rounds", "type": "number", "default": 2, "min": 1, "max": 20},
            {"name": "phase_3_rounds", "label": "Phase 3 Rounds", "type": "number", "default": 2, "min": 1, "max": 20},
        ]
    },
    "sequential_search": {
        "name": "Sequential Thinking + Search",
        "description": "3-phase thinking with web search integration",
        "generator": generate_sequential_thinking_search_prompt,
        "params": [
            {"name": "phase_1_rounds", "label": "Phase 1 Rounds", "type": "number", "default": 6, "min": 1, "max": 20},
            {"name": "phase_2_rounds", "label": "Phase 2 Rounds", "type": "number", "default": 4, "min": 1, "max": 20},
            {"name": "phase_3_rounds", "label": "Phase 3 Rounds", "type": "number", "default": 2, "min": 1, "max": 20},
            {"name": "min_searches", "label": "Min Searches", "type": "number", "default": 8, "min": 1, "max": 50},
            {"name": "max_searches", "label": "Max Searches", "type": "number", "default": 16, "min": 1, "max": 50},
        ]
    },
    "simpler_search": {
        "name": "Simple Search + Think",
        "description": "Simpler search with sequential verification",
        "generator": generate_simpler_search_prompt,
        "params": [
            {"name": "thinking_rounds", "label": "Thinking Rounds", "type": "number", "default": 5, "min": 1, "max": 20},
            {"name": "min_searches", "label": "Min Searches", "type": "number", "default": 8, "min": 1, "max": 50},
            {"name": "max_searches", "label": "Max Searches", "type": "number", "default": 16, "min": 1, "max": 50},
        ]
    }
}


def get_prompt_config() -> Dict[str, Any]:
    """Return the full prompt configuration for the frontend."""
    return {
        "static": STATIC_PROMPTS,
        "configurable": {
            key: {
                "name": val["name"],
                "description": val["description"],
                "params": val["params"]
            }
            for key, val in CONFIGURABLE_PROMPTS.items()
        }
    }


def generate_prompt(prompt_id: str, params: Dict[str, Any] = None) -> str:
    """Generate a prompt by ID with optional parameters."""
    if prompt_id in STATIC_PROMPTS:
        return STATIC_PROMPTS[prompt_id]["content"]
    
    if prompt_id in CONFIGURABLE_PROMPTS:
        generator = CONFIGURABLE_PROMPTS[prompt_id]["generator"]
        if params:
            return generator(**params)
        return generator()
    
    raise ValueError(f"Unknown prompt ID: {prompt_id}")
