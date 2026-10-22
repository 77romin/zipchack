import requests


def search_workplace(query, api_key):
    headers = {
        "Authorization": f"KakaoAK {api_key}",
    }

    # 주소로 먼저 검색합니다.
    response = requests.get(
        "https://dapi.kakao.com/v2/local/search/address.json",
        headers=headers,
        params={"query": query, "size": 5},
        timeout=10,
    )
    response.raise_for_status()

    addresses = response.json().get("documents", [])

    if addresses:
        return [
            {
                "name": item["address_name"],
                "address": item["address_name"],
                "latitude": float(item["y"]),
                "longitude": float(item["x"]),
            }
            for item in addresses
        ]

    # 주소 검색 결과가 없으면 장소명으로 검색합니다.
    response = requests.get(
        "https://dapi.kakao.com/v2/local/search/keyword.json",
        headers=headers,
        params={"query": query, "size": 5},
        timeout=10,
    )
    response.raise_for_status()

    places = response.json().get("documents", [])

    return [
        {
            "name": item["place_name"],
            "address": (
                item["road_address_name"]
                or item["address_name"]
            ),
            "latitude": float(item["y"]),
            "longitude": float(item["x"]),
        }
        for item in places
    ]