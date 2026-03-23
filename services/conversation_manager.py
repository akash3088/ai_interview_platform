class ConversationManager:

    def __init__(self, role, level):
        self.role = role
        self.level = level
        self.question_history = []
        self.answer_history = []
        self.max_questions = 4

    def add_interaction(self, question, answer):
        self.question_history.append(question)
        self.answer_history.append(answer)

    def should_finish(self):
        return len(self.question_history) >= self.max_questions

    def get_context(self):
        context = ""

        for i, q in enumerate(self.question_history):
            context += f"Q{i+1}: {q}\n"
            if i < len(self.answer_history):
                context += f"A{i+1}: {self.answer_history[i]}\n"

        return context
    