import requests
import openai
from src.backend.utils.configs import Config


class LinkedInParser:
    def __init__(self, user_link: str):
        self.user_link = user_link
        self.configs = Config.load_config()
        self.generect_url = "https://api.generect.com/api/linkedin/leads/by_link/"
        self.headers = {
            "Authorization": f"Token {self.configs.linkedinparser.API_KEY.get_secret_value()}",
            "Content-Type": "application/json"
        }
        openai.api_key = self.configs.openai.API_KEY.get_secret_value()

    def _fetch_user_data(self) -> dict:
        payload = {
            "comments": False,
            "inexact_company": False,
            "people_also_viewed": False,
            "posts": False,
            "url": self.user_link
        }

        response = requests.post(self.generect_url, headers=self.headers, json=payload)
        user = response.json()

        return user.get("lead", {})

    def _parse_companies(self, jobs: list) -> list:
        return [job.get("company_name") for job in jobs if job.get("company_name")]

    def _parse_educations(self, educations: list) -> list:
        education_list = []
        for edu in educations:
            education_list.append({
                "university": edu.get("university_name"),
                "degree": edu.get("degree"),
                "field": edu.get("fields_of_study"),
                "start": edu.get("started_on", {}).get("year"),
                "end": edu.get("ended_on", {}).get("year")
            })
        return education_list

    def _describe_company(self, company_name: str, max_tokens: int = 400) -> str | None:
        if not company_name:
            return None

        system_msg = (
            "You are an assistant who describes the company concisely and accurately. "
            "Give a brief professional description of the company, indicate the field of activity, product/service capabilities."
        )
        user_prompt = f"Describe the company {company_name}."

        try:
            llm_response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            return llm_response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return None

    def parse_user(self) -> dict:
        lead = self._fetch_user_data()

        companies = self._parse_companies(lead.get("jobs", []))
        educations = self._parse_educations(lead.get("educations", []))

        company_data = []
        for company in companies:
            description = self._describe_company(company)
            company_data.append({
                "name": company,
                "description": description
            })

        return {
            "companies": company_data,
            "educations": educations
        }


# if __name__ == "__main__":
#     user_link = "https://www.linkedin.com/in/vitaliy-butko-a846b5270/"
#     linkedin = LinkedInParser(user_link)
#     user_info = linkedin.parse_user()

#     print(json.dumps(user_info, indent=2, ensure_ascii=False))
