# import redis
# import urllib.parse

# username = "default"  # usually 'default' for Leapcell
# password = urllib.parse.quote_plus('Ae00000X6xChO9yl9y80Gu1A2/fheoYoXAjzpTHsgd/ZKpRGvmwFTv9Bh6R+LzTIqkaZUyF')

# r = redis.Redis(
#     host='budegt_agent-jxio-bead-760321.leapcell.cloud',
#     port=6379,
#     username=username,       # <-- important if ACL is enabled
#     password=password,
#     ssl=True,
#     ssl_cert_reqs=None,      # skip certificate verification
#     decode_responses=True
# )

# # Test
# r.set('answer', '42')
# print(r.get('answer'))  # should print 42
