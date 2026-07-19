# app/agents/tool_router.py
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Charge le .env depuis la racine du projet
load_dotenv()

class ToolRouter:
    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "nvidia")
        
        print(f"🚀 [ToolRouter] Initialisé avec le provider : {self.provider.upper()}")

        if self.provider == "nvidia":
            self.client = AsyncOpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=os.getenv("NVIDIA_API_KEY")
            )
            self.fast_model = os.getenv("NVIDIA_MODEL", "qwen/qwen2.5-72b-instruct")
            self.smart_model = self.fast_model
            
        else:  # Alibaba DashScope
            self.client = AsyncOpenAI(
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.getenv("DASHSCOPE_API_KEY")
            )
            self.fast_model = "qwen-plus"
            self.smart_model = "qwen-max"

    async def generate(self, prompt: str, system_prompt: str, use_smart: bool = False):
        """Génère du texte avec le modèle approprié"""
        model = self.smart_model if use_smart else self.fast_model
        
        print(f"🧠 [ToolRouter] Appel de {model} via {self.provider}...")
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ [ToolRouter] Erreur API : {e}")
            return None

    async def test_connection(self):
        """Test simple pour vérifier que la connexion API fonctionne"""
        print(f" [ToolRouter] Test de connexion avec {self.provider}...")
        result = await self.generate(
            prompt="Dis simplement 'Connexion réussie !'",
            system_prompt="Tu es un assistant de test.",
            use_smart=False
        )
        if result:
            print(f"✅ [ToolRouter] Connexion réussie ! Réponse : {result}")
        else:
            print(f"❌ [ToolRouter] Échec de la connexion.")
        return result