import os
import json
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

PURINCASH_API_KEY = os.getenv("ps_live_0585c049183e39d4b4a5a25bed68e26d8422949ef0d27ae9fc5b6ea7f7cfead1")
CALLBACK_URL = os.getenv("https://odarp.pythonanywhere.com/webhook-purincash")
BASE_URL = "https://api.purincash.com/v1"

# === PRODUTOS ===
PRODUTOS = {
    "fotos": {
        "nome": "Pack de Fotos",
        "valor_centavos": 500,   # R$ 5,00
        "entrega": "https://drive.google.com/drive/folders/1GPPoCyVd2k1XgEC_WWrzi43LciSlVtQF?usp=sharing"
    },
    "videos": {
        "nome": "Pack de Vídeos",
        "valor_centavos": 1200,  # R$ 12,00
        "entrega": "https://drive.google.com/drive/folders/1M7UtYvfNt5Ue_m43RnLLyhCRNZ0txAwM?usp=sharing"
    }
}


def gerar_cobranca(produto_id, usuario_id, nome_usuario, email_usuario="cliente@exemplo.com"):
    produto = PRODUTOS.get(produto_id)
    if not produto:
        return {"erro": "Produto não encontrado"}

    metadata = json.dumps({
        "usuario_id": usuario_id,
        "produto_id": produto_id,
        "produto_nome": produto["nome"]
    })

    headers = {
        "Authorization": f"Bearer {PURINCASH_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "valueCents": produto["valor_centavos"],
        "description": produto["nome"],
        "callbackUrl": CALLBACK_URL,
        "customer": {
            "name": nome_usuario,
            "email": email_usuario
        },
        "metadata": metadata
    }

    try:
        resposta = requests.post(
            f"{BASE_URL}/charges",
            json=payload,
            headers=headers,
            timeout=15
        )
        
        if resposta.status_code in (200, 201):
            dados = resposta.json()
            dados["produto_nome"] = produto["nome"]
            dados["valor_real"] = produto["valor_centavos"] / 100
            return dados
        else:
            print(f"Erro PurinCash: {resposta.status_code} - {resposta.text}")
            return {"erro": f"Falha na cobrança: {resposta.status_code}"}
            
    except Exception as e:
        print(f"Erro de conexão: {str(e)}")
        return {"erro": "Falha de conexão com o gateway"}


def validar_assinatura(corpo_requisicao, assinatura_recebida):
    segredo = os.getenv("PURINCASH_WEBHOOK_SECRET")
    if not segredo:
        return False

    # Garante que o corpo seja bytes (pode chegar como str em alguns frameworks)
    if isinstance(corpo_requisicao, str):
        corpo_requisicao = corpo_requisicao.encode("utf-8")

    assinatura_esperada = hmac.new(
        segredo.encode("utf-8"),
        corpo_requisicao,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(assinatura_esperada, assinatura_recebida)