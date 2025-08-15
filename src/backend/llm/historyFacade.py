class HistoryFacade:

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(HistoryFacade, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.chat_history = []

    def add_user_query(self, query: str):
        self.chat_history.append({
            "role": "user",
            "content": [{
                "type": "text",
                "text": query
            }]
        })

    def add_assistant_message(self, message: str):
        self.chat_history.append({
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": message
            }]
        })

    def add_system_message(self, message: str):
        self.chat_history.append({
            "role": "system",
            "content": [{
                "type": "text",
                "text": message
            }]
        })

    def get_history(self):
        return self.chat_history