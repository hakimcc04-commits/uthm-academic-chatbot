from nlp import get_bot_response

while True:
    user_input = input("Student: ")

    if user_input.lower() in ["exit", "quit"]:
        break

    response = get_bot_response(user_input)
    print("Chatbot:", response)