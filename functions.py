from api.intercom import assign_conversation_to_human


functions = [
    {
        "name": "assign_conversation_to_human",
        "description": "Assigns the conversation to a human representative.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": ["unknown_answer", "customer_request"],
                    "description": "The reason for the assignment.",
                },
            },
            "required": ["reason"],
        },
    }
]


async def execute_function_call(message, conversation_id):
    if message["function_call"]["name"] == "assign_conversation_to_human":
        results = await assign_conversation_to_human(conversation_id)
    else:
        results = f"Error: function {message['function_call']['name']} does not exist"
    return results
