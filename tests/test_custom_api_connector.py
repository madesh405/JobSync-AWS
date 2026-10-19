import unittest
from unittest.mock import patch

from custom_api_connector import (
    _number_or_none,
    get_path_value,
    normalize_config,
    record_to_job,
    validate_endpoint,
)


def public_dns_result():
    return [
        (
            2,
            1,
            6,
            "",
            ("8.8.8.8", 443),
        )
    ]


class CustomApiConnectorTests(unittest.TestCase):
    @patch("custom_api_connector.socket.getaddrinfo", return_value=public_dns_result())
    def test_accepts_public_https_endpoint(self, mocked_dns):
        self.assertEqual(
            validate_endpoint("https://api.example.com/jobs"),
            "https://api.example.com/jobs",
        )
        mocked_dns.assert_called_once()

    def test_rejects_http_endpoint(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_endpoint("http://api.example.com/jobs")

    def test_rejects_private_literal_ip(self):
        with self.assertRaisesRegex(ValueError, "private or reserved"):
            validate_endpoint("https://127.0.0.1/jobs")

    def test_rejects_credentials_in_endpoint(self):
        with self.assertRaisesRegex(ValueError, "Credentials"):
            validate_endpoint("https://user:pass@api.example.com/jobs")

    def test_resolves_nested_json_paths(self):
        payload = {
            "data": {
                "jobs": [
                    {"title": "Backend Engineer"},
                    {"title": "Cloud Engineer"},
                ]
            }
        }
        self.assertEqual(
            get_path_value(payload, "data.jobs.1.title"),
            "Cloud Engineer",
        )

    @patch("custom_api_connector.socket.getaddrinfo", return_value=public_dns_result())
    def test_validates_field_mapping_and_page_limit(self, mocked_dns):
        source = {
            "api_config": {
                "endpoint": "https://api.example.com/jobs",
                "records_path": "data.jobs",
                "fields": {
                    "title": "position.title",
                    "company": "employer.name",
                    "apply_url": "url",
                },
                "pagination": {
                    "type": "PAGE",
                    "page_parameter": "page",
                    "start_page": 0,
                    "max_pages": 3,
                },
            }
        }
        config = normalize_config(source)
        self.assertEqual(config["records_path"], "data.jobs")
        self.assertEqual(config["pagination"]["max_pages"], 3)
        mocked_dns.assert_called()

    @patch("custom_api_connector.socket.getaddrinfo", return_value=public_dns_result())
    def test_rejects_more_than_ten_pages(self, mocked_dns):
        source = {
            "api_config": {
                "endpoint": "https://api.example.com/jobs",
                "fields": {"title": "title", "company": "company"},
                "pagination": {
                    "type": "PAGE",
                    "page_parameter": "page",
                    "start_page": 1,
                    "max_pages": 11,
                },
            }
        }
        with self.assertRaisesRegex(ValueError, "between 1 and 10 pages"):
            normalize_config(source)

    def test_salary_parser_handles_strings_and_invalid_values(self):
        self.assertEqual(_number_or_none("$120,000"), 120000.0)
        self.assertIsNone(_number_or_none("not published"))

    def test_maps_custom_record_to_normalized_job(self):
        record = {
            "id": "abc-123",
            "title": "Backend Engineer",
            "company": "Example Corp",
            "location": "Remote",
            "type": "full-time",
            "apply": "https://jobs.example.com/abc-123",
        }
        job = record_to_job(
            record,
            "custom-example-abc123",
            {
                "source_id": "id",
                "title": "title",
                "company": "company",
                "location": "location",
                "employment_type": "type",
                "apply_url": "apply",
            },
        )
        self.assertEqual(job.source, "custom-example-abc123")
        self.assertEqual(job.source_id, "abc-123")
        self.assertEqual(job.employment_type, "FULL_TIME")
        self.assertEqual(job.apply_url, record["apply"])
        self.assertTrue(job.canonical_job_id)


if __name__ == "__main__":
    unittest.main()
