
from openai import OpenAI
import numpy as np
from src.backend.utils.configs import Config

class TextVectorizer:
    def __init__(self):
        self.configs = Config().load_config()
        self.api_key = self.configs.openai.API_KEY.get_secret_value()
        self.client = OpenAI(api_key=self.api_key)
        self.model_name = "text-embedding-3-small"
    
    def vectorize(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(
            input=text,
            model=self.model_name
        )
        return np.array(response.data[0].embedding)
    
    def vectorize_batch(self, texts: list[str]) -> np.ndarray:
        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name
        )
        return np.array([item.embedding for item in response.data])