from openai import OpenAI
import os
import time
import base64
import mimetypes
import dashscope
from dashscope import ImageSynthesis
from dotenv import load_dotenv

load_dotenv()

class ToolRouter:
    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "alibaba")
        print(f"🚀 [ToolRouter] Provider : {self.provider.upper()}")

        # ✅ NOUVEAU : Métadonnées du dernier appel (pour la Timeline UI)
        self.last_system_prompt = None
        self.last_user_prompt = None
        self.last_response = None
        self.last_duration_sec = None
        self.last_tokens = {"prompt": None, "completion": None, "total": None}
        self.last_model = None
        
        if self.provider == "nvidia":
            self.client = OpenAI(
                api_key=os.getenv("NVIDIA_API_KEY"),
                base_url="https://integrate.api.nvidia.com/v1"
            )
            self.model = os.getenv("NVIDIA_MODEL", "qwen/qwen3.5-122b-a10b")
        else:
            # ✅ CORRECTION CRITIQUE : dashscope-INTL pour l'international
            self.client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
            )
            # ✅ Modèle officiel daté (plus stable)
            #self.model = "qwen-plus-2025-12-01"
            #self.model = "qwen3.5-397b-a17b"
            self.model = "qwen3-max-2026-01-23"

            # Config du SDK dashscope natif (nécessaire pour la génération
            # d'images/vidéo, qui n'est pas exposée par l'endpoint
            # "compatible OpenAI" utilisé pour le chat) — même clé, même
            # région internationale que le reste.
            dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
            dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
            
            
    
    def generate(self, prompt: str, system_prompt: str) -> str:
        """Version synchrone"""
        print(f"🧠 [ToolRouter] Appel de {self.model} via {self.provider}")

        # ✅ Mémoriser le prompt utilisé (pour affichage dans la Timeline)
        self.last_system_prompt = system_prompt
        self.last_user_prompt = prompt
        self.last_model = self.model

        start = time.time()
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            self.last_duration_sec = round(time.time() - start, 2)

            # ✅ Capturer la consommation de tokens si disponible
            usage = getattr(completion, "usage", None)
            if usage:
                self.last_tokens = {
                    "prompt": getattr(usage, "prompt_tokens", None),
                    "completion": getattr(usage, "completion_tokens", None),
                    "total": getattr(usage, "total_tokens", None),
                }
            else:
                self.last_tokens = {"prompt": None, "completion": None, "total": None}

            content = completion.choices[0].message.content.strip()
            self.last_response = content
            return content
        except Exception as e:
            self.last_duration_sec = round(time.time() - start, 2)
            print(f"❌ [ToolRouter] Erreur : {e}")
            return None
    
    def generate_vision(self, prompt: str, system_prompt: str, image_path: str,
                         vision_model: str = "qwen3.7-plus") -> str:
        """Appel multimodal (texte + image), utilisé pour l'extraction de
        style à partir des images de référence. Modèle séparé du texte
        (qwen3-max n'est pas vision-capable) — quota gratuit indépendant."""
        print(f"🖼️ [ToolRouter] Appel vision de {vision_model} via {self.provider}")

        self.last_system_prompt = system_prompt
        self.last_user_prompt = prompt
        self.last_model = vision_model

        start = time.time()
        try:
            mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            with open(image_path, "rb") as f:
                b64_image = base64.b64encode(f.read()).decode("utf-8")
            data_url = f"data:{mime_type};base64,{b64_image}"

            completion = self.client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ]},
                ],
                temperature=0.5,
            )
            self.last_duration_sec = round(time.time() - start, 2)

            usage = getattr(completion, "usage", None)
            if usage:
                self.last_tokens = {
                    "prompt": getattr(usage, "prompt_tokens", None),
                    "completion": getattr(usage, "completion_tokens", None),
                    "total": getattr(usage, "total_tokens", None),
                }
            else:
                self.last_tokens = {"prompt": None, "completion": None, "total": None}

            content = completion.choices[0].message.content.strip()
            self.last_response = content
            return content
        except Exception as e:
            self.last_duration_sec = round(time.time() - start, 2)
            print(f"❌ [ToolRouter] Erreur vision : {e}")
            return None

    def generate_image(self, prompt: str, model: str = "wan2.2-t2i-plus", size: str = "1024*1024") -> dict:
        """Génère une image (text-to-image) via l'API DashScope native (Wan/Qwen).
        Distinct de generate()/generate_vision() : ce n'est pas un chat completion,
        c'est un appel de synthèse d'image asynchrone (create task -> poll résultat).
        Retourne {"url": ..., "duration_sec": ..., "model": ...} ou None en cas d'échec.
        """
        print(f"🎨 [ToolRouter] Génération image via {model}")
        self.last_model = model
        self.last_user_prompt = prompt
        self.last_system_prompt = None

        start = time.time()
        try:
            response = ImageSynthesis.async_call(
                model=model,
                prompt=prompt,
                n=1,
                size=size,
            )
            result = ImageSynthesis.wait(response)
            duration = round(time.time() - start, 2)
            self.last_duration_sec = duration
            self.last_tokens = {"prompt": None, "completion": None, "total": None}

            if result.status_code == 200 and result.output.results:
                image_url = result.output.results[0].url
                self.last_response = image_url
                return {"url": image_url, "duration_sec": duration, "model": model}
            else:
                print(f"❌ [ToolRouter] Échec génération image : {result.message if hasattr(result, 'message') else result}")
                return None
        except Exception as e:
            self.last_duration_sec = round(time.time() - start, 2)
            print(f"❌ [ToolRouter] Erreur génération image : {e}")
            return None

    def test_connection(self):
        """Test simple"""
        print(f"🔌 Test avec {self.provider}...")
        result = self.generate(
            prompt="Dis simplement 'Connexion Alibaba réussie !'",
            system_prompt="Tu es un assistant de test."
        )
        if result:
            print(f"✅ Connexion OK ! Réponse : {result}")
        else:
            print(f"❌ Échec de connexion.")
        return result

tool_router = ToolRouter()