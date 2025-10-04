from src.backend.parser.linkedin_parser import LinkedInParser
import json
import asyncio

user_link = "https://www.linkedin.com/in/vitaliy-butko-a846b5270/"
linkedin = LinkedInParser()
user_info = asyncio.run(linkedin.parse_user(user_link))

print("-_"*20)
print(type(user_info))
print(user_info)