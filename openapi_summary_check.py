import json, urllib.request as u
doc = json.loads(u.urlopen("http://127.0.0.1:9000/openapi.json").read())
print(doc["paths"]["/reservations"]["post"]["summary"])
print(doc["paths"]["/reservations/pay"]["post"]["summary"])
