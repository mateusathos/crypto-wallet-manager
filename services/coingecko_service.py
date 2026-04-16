import os
import requests

BASE_URL = "https://api.coingecko.com/api/v3"


def _get_headers():
    api_key = os.getenv("COINGECKO_API_KEY")
    if api_key:
        return {"x-cg-demo-api-key": api_key}
    return {}


def simple_price(crypto_ids, vs_currencies="brl"):
    url = f"{BASE_URL}/simple/price"
    params = {
        "ids": ",".join(crypto_ids),
        "vs_currencies": vs_currencies
    }

    response = requests.get(
        url,
        headers=_get_headers(),
        params=params,
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def coin_list():
    """Retorna a lista de todas as moedas suportadas (ID, name, symbol)."""
    url = f"{BASE_URL}/coins/list"
    resp = requests.get(url, headers=_get_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


def coins_markets(vs_currency="brl", ids=None, order="market_cap_desc", per_page=100, page=1):
    """
    Retorna dados de mercado detalhados (preço, volume, market cap).
    - vs_currency: moeda de comparação (ex: brl)
    - ids: lista de crypto IDs opcionais (ex: 'bitcoin,ethereum')
    """
    url = f"{BASE_URL}/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "order": order,
        "per_page": per_page,
        "page": page,
        "sparkline": False
    }
    if ids:
        params["ids"] = ids

    resp = requests.get(url, headers=_get_headers(), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def coin_details(coin_id):
    """Retorna dados completos da cripto, incluindo descrição, sites, redes sociais etc."""
    url = f"{BASE_URL}/coins/{coin_id}"
    resp = requests.get(url, headers=_get_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


def coin_history(coin_id, date):
    """
    Retorna dados históricos de preço por data (formato: dd-mm-yyyy).
    Exemplo: '30-12-2024'
    """
    url = f"{BASE_URL}/coins/{coin_id}/history"
    params = {"date": date}
    resp = requests.get(url, headers=_get_headers(), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def market_chart(coin_id, vs_currency="brl", days=30):
    """
    Gráfico de preços (timestamp + preço) pelo número de dias.
    - days pode ser: 1, 7, 30, 'max' etc.
    """
    url = f"{BASE_URL}/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": days}
    resp = requests.get(url, headers=_get_headers(), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()