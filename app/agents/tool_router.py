from openai import OpenAI
import os
import time
import base64
import mimetypes
import dashscope
from dashscope import ImageSynthesis, MultiModalConversation
from dashscope.aigc.image_generation import ImageGeneration
from dashscope.api_entities.dashscope_response import Message
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

load_dotenv()

# Pool partagé pour imposer un plafond de temps sur les appels SDK bloquants
# (ImageSynthesis.wait, etc.) qui n'exposent pas de paramètre de timeout —
# indépendant de ce que fait le SDK en interne, ça garantit qu'on ne reste
# JAMAIS bloqué indéfiniment sans la moindre erreur visible.
# ⚠️ max_workers volontairement large : un appel qui dépasse le plafond
# continue de tourner en arrière-plan (impossible de le tuer de force côté
# Python) — s'il n'y avait que peu de workers, plusieurs appels bloqués
# finiraient par empêcher les NOUVEAUX appels de démarrer, ce qui annulerait
# tout l'intérêt du timeout.
_blocking_call_executor = ThreadPoolExecutor(max_workers=20)


def _run_with_timeout(func, timeout_sec, *args, **kwargs):
    """Exécute func(*args, **kwargs) dans un thread séparé, avec un plafond
    de temps strict. Lève TimeoutError si le délai est dépassé — l'appel SDK
    continue en arrière-plan (on ne peut pas le tuer de force), mais on ne
    reste plus jamais bloqué à attendre sans le savoir."""
    future = _blocking_call_executor.submit(func, *args, **kwargs)
    return future.result(timeout=timeout_sec)

# Trois clés distinctes, pour répartir les appels sur des comptes/quotas
# différents si besoin (ex: compte "coupon" pour les images/vidéo, compte
# "free tier" pour le texte). Repli automatique sur DASHSCOPE_API_KEY tant
# qu'un champ spécifique n'est pas renseigné, pour ne rien casser pendant
# la transition.
REASONING_API_KEY = os.getenv("DASHSCOPE_API_KEY_REASONING") or os.getenv("DASHSCOPE_API_KEY")
IMAGES_API_KEY = os.getenv("DASHSCOPE_API_KEY_IMAGES") or os.getenv("DASHSCOPE_API_KEY")
VIDEO_API_KEY = os.getenv("DASHSCOPE_API_KEY_VIDEO") or os.getenv("DASHSCOPE_API_KEY")

# Modèles texte->image disponibles pour Personnages et Décors. wan2.2-t2i-plus reste le
# défaut (déjà validé, quota déjà bien entamé) — wan2.6/2.7 sont là pour comparer.
AVAILABLE_IMAGE_MODELS = ["wan2.2-t2i-plus", "wan2.6-t2i", "wan2.7-image-pro"]
DEFAULT_IMAGE_MODEL = "wan2.2-t2i-plus"

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
                base_url="https://integrate.api.nvidia.com/v1",
                timeout=90.0,  # évite un blocage silencieux et indéfini si l'appel reste bloqué
            )
            self.model = os.getenv("NVIDIA_MODEL", "qwen/qwen3.5-122b-a10b")
        else:
            # ✅ CORRECTION CRITIQUE : dashscope-INTL pour l'international
            # Texte + vision (compréhension d'image, pas génération) -> clé "reasoning"
            self.client = OpenAI(
                api_key=REASONING_API_KEY,
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                timeout=90.0,  # idem : jamais d'attente indéfinie sans erreur visible
            )
            # ✅ Modèle officiel daté (plus stable)
            #self.model = "qwen-plus-2025-12-01"
            #self.model = "qwen3.5-397b-a17b"
            self.model = "qwen3-max-2026-01-23"

            # Config du SDK dashscope natif (nécessaire pour la génération
            # d'images/vidéo, qui n'est pas exposée par l'endpoint
            # "compatible OpenAI" utilisé pour le chat) — la clé par défaut du
            # SDK reste celle du texte ; generate_image/generate_image_edit
            # passent explicitement IMAGES_API_KEY à chaque appel, et
            # scene_generator.py passe explicitement VIDEO_API_KEY.
            dashscope.api_key = REASONING_API_KEY
            dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
            
            
    
    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.7) -> str:
        """Version synchrone. `temperature` par défaut à 0.7 (comportement
        inchangé pour tous les agents existants) — certains agents (ex:
        Showrunner) peuvent monter ce paramètre pour plus de divergence
        créative, quand la fidélité stricte n'est pas la priorité."""
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
                temperature=temperature
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

    def generate_vision_multi(self, prompt: str, system_prompt: str, image_labels: list,
                               vision_model: str = "qwen3.7-plus") -> str:
        """Appel multimodal avec PLUSIEURS images labellisées (qwen3.7-plus
        accepte jusqu'à ~20 images). image_labels : liste de (label_text,
        image_path) — un texte de repère juste avant chaque image, pour que
        le modèle sache distinguer "personnage A closeup" de "décor" etc.
        Utilise dashscope.MultiModalConversation (pas le client compatible
        OpenAI) car le format de contenu entrelacé texte/image est celui
        déjà confirmé fonctionnel ailleurs dans ce projet (édition d'image).
        Retourne le texte de la réponse (typiquement du JSON à parser côté
        appelant), ou None en cas d'échec — ne bloque jamais."""
        print(f"🖼️ [ToolRouter] Appel vision multi-images ({len(image_labels)} images) de {vision_model} via {self.provider}")

        self.last_system_prompt = system_prompt
        self.last_user_prompt = prompt
        self.last_model = vision_model

        start = time.time()
        try:
            content = []
            for label, path in image_labels:
                if label:
                    content.append({"text": label})
                mime_type = mimetypes.guess_type(path)[0] or "image/png"
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                content.append({"image": f"data:{mime_type};base64,{b64}"})
            content.append({"text": prompt})

            response = MultiModalConversation.call(
                api_key=REASONING_API_KEY,
                model=vision_model,
                messages=[
                    {"role": "system", "content": [{"text": system_prompt}]},
                    {"role": "user", "content": content},
                ],
                request_timeout=600,
            )
            self.last_duration_sec = round(time.time() - start, 2)

            if response.status_code == 200:
                text = response.output.choices[0].message.content[0]["text"]
                self.last_response = text
                return text
            print(f"❌ [ToolRouter] Échec vision multi-images : {getattr(response, 'message', response)}")
            return None
        except Exception as e:
            self.last_duration_sec = round(time.time() - start, 2)
            print(f"❌ [ToolRouter] Erreur vision multi-images : {e}")
            return None

    def generate_image(self, prompt: str, model: str = "wan2.2-t2i-plus", size: str = "1024*1024") -> dict:
        """Génère une image (text-to-image) via l'API DashScope native (Wan/Qwen).
        Distinct de generate()/generate_vision() : ce n'est pas un chat completion.

        Deux mécanismes selon le modèle, confirmés séparément :
        - wan2.2-t2i-plus : dashscope.ImageSynthesis (async_call + wait) — INCHANGÉ,
          c'est le modèle par défaut déjà validé, on ne touche pas à ce qui marche.
        - wan2.6-t2i / wan2.7-image-pro : dashscope.aigc.image_generation.ImageGeneration
          (Message + .call() synchrone), confirmé par la documentation officielle pour
          wan2.6-t2i ; wan2.7-image-pro partage la même classe (déjà utilisée avec succès
          pour l'édition d'image dans ce projet).

        Retourne {"url": ..., "duration_sec": ..., "model": ...} ou None en cas d'échec.
        """
        print(f"🎨 [ToolRouter] Génération image via {model}")
        self.last_model = model
        self.last_user_prompt = prompt
        self.last_system_prompt = None

        start = time.time()

        if model in ("wan2.6-t2i", "wan2.7-image-pro"):
            try:
                message = Message(role="user", content=[{"text": prompt}])
                rsp = ImageGeneration.call(
                    model=model,
                    api_key=IMAGES_API_KEY,
                    messages=[message],
                    negative_prompt="",
                    prompt_extend=True,
                    watermark=False,
                    n=1,
                    size=size,
                    request_timeout=600,
                )
                duration = round(time.time() - start, 2)
                self.last_duration_sec = duration
                self.last_tokens = {"prompt": None, "completion": None, "total": None}

                if rsp.status_code != 200:
                    print(f"❌ [ToolRouter] Échec génération image ({model}) : {getattr(rsp, 'message', rsp)}")
                    return None

                # Structure de réponse non confirmée avec un vrai appel pour ce cas précis
                # (texte->image pur) — on tente les deux formes les plus probables vu les
                # autres endpoints DashScope déjà rencontrés dans ce projet.
                image_url = None
                try:
                    image_url = rsp.output.choices[0].message.content[0]["image"]
                except (AttributeError, KeyError, IndexError, TypeError):
                    try:
                        image_url = rsp.output.results[0].url
                    except (AttributeError, KeyError, IndexError, TypeError):
                        pass

                if image_url:
                    self.last_response = image_url
                    return {"url": image_url, "duration_sec": duration, "model": model}

                print(f"❌ [ToolRouter] Réponse reçue mais structure inattendue ({model}), réponse brute : {rsp}")
                return None
            except Exception as e:
                self.last_duration_sec = round(time.time() - start, 2)
                print(f"❌ [ToolRouter] Erreur génération image ({model}) : {e}")
                return None

        # --- Chemin par défaut, inchangé : wan2.2-t2i-plus via ImageSynthesis ---
        try:
            response = ImageSynthesis.async_call(
                api_key=IMAGES_API_KEY,
                model=model,
                prompt=prompt,
                n=1,
                size=size,
            )
            result = _run_with_timeout(ImageSynthesis.wait, 120, response, api_key=IMAGES_API_KEY)
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
        except FutureTimeoutError:
            self.last_duration_sec = round(time.time() - start, 2)
            print(f"❌ [ToolRouter] Timeout génération image ({model}) : dépassement de 120s, l'appel est abandonné côté app "
                  f"(la tâche continue peut-être côté serveur DashScope, mais on n'attend plus).")
            return None
        except Exception as e:
            self.last_duration_sec = round(time.time() - start, 2)
            print(f"❌ [ToolRouter] Erreur génération image : {e}")
            return None

    def generate_image_edit(self, prompt: str, image_paths: list, model: str = "qwen-image-edit-max",
                             size: str = "1024*1024") -> dict:
        """Édition/composition d'image à partir d'une ou plusieurs images de
        référence locales (ex: construire le Model Sheet à partir du portrait
        choisi). Deux familles de modèles, deux mécanismes DashScope distincts
        sous le capot — le choix du modèle route automatiquement vers le bon :
        - Wan (wan*)        -> dashscope.ImageSynthesis
        - Qwen-Image (qwen*) -> dashscope.MultiModalConversation
        Les images locales sont encodées en base64 (DashScope ne peut pas
        atteindre un localhost pendant le développement)."""
        print(f"🖌️ [ToolRouter] Édition image via {model} ({size})")
        self.last_model = model
        self.last_user_prompt = prompt
        self.last_system_prompt = None

        start = time.time()
        try:
            data_urls = []
            for path in image_paths:
                mime_type = mimetypes.guess_type(path)[0] or "image/png"
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                data_urls.append(f"data:{mime_type};base64,{b64}")

            if model.startswith("wan"):
                # Wan (wan2.7-image-pro) utilise une classe et un appel différents
                # de la famille Qwen-Image — confirmé via l'exemple officiel
                # partagé : dashscope.aigc.image_generation.ImageGeneration,
                # appel SYNCHRONE (.call(), pas async_call()+wait()), messages
                # construits avec la classe Message.
                content = [{"image": u} for u in data_urls] + [{"text": prompt}]
                message = Message(role="user", content=content)

                rsp = ImageGeneration.call(
                    model=model,
                    api_key=IMAGES_API_KEY,
                    messages=[message],
                    n=1,
                    size=size,
                    request_timeout=600,
                )
                self.last_duration_sec = round(time.time() - start, 2)

                if rsp.status_code != 200:
                    print(f"❌ [ToolRouter] Échec édition image (Wan) : {getattr(rsp, 'message', rsp)}")
                    return None

                # La doc officielle ne détaille pas la structure exacte de la
                # réponse (juste print(rsp) dans l'exemple) — on tente les deux
                # formes les plus probables vu les autres endpoints DashScope.
                url = None
                try:
                    url = rsp.output.choices[0].message.content[0]["image"]
                except (AttributeError, KeyError, IndexError, TypeError):
                    try:
                        url = rsp.output.results[0].url
                    except (AttributeError, KeyError, IndexError, TypeError):
                        pass

                if url:
                    self.last_response = url
                    return {"url": url, "duration_sec": self.last_duration_sec, "model": model}

                print(f"❌ [ToolRouter] Réponse Wan reçue mais structure inattendue, réponse brute : {rsp}")
                return None
            else:
                content = [{"image": u} for u in data_urls] + [{"text": prompt}]
                response = MultiModalConversation.call(
                    api_key=IMAGES_API_KEY,
                    model=model,
                    messages=[{"role": "user", "content": content}],
                    n=1,
                    watermark=False,
                    size=size,
                    request_timeout=600,
                )
                self.last_duration_sec = round(time.time() - start, 2)
                if response.status_code == 200:
                    url = response.output.choices[0].message.content[0]["image"]
                    self.last_response = url
                    return {"url": url, "duration_sec": self.last_duration_sec, "model": model}
                print(f"❌ [ToolRouter] Échec édition image (Qwen-Image) : {getattr(response, 'message', response)}")
                return None
        except Exception as e:
            self.last_duration_sec = round(time.time() - start, 2)
            print(f"❌ [ToolRouter] Erreur édition image : {e}")
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