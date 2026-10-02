#!/usr/bin/env python3
"""Tests for extract_json_result() — the function that scans executor
output for an embedded result JSON.

Regression driver: Work Order ec326936-0230-4a38-8a7a-4a2f80b1b627
(02.10.2026) produced exit 0, embedded its result in a ```json block
inside the `result` field of the --output-format json wrapper, but the
diff artifact's content string contained
  "{ children }: { children: React.ReactNode }"
which broke the old brace-counting scanner → None → result_missing.

Stdlib-only (unittest), no dependency install required.

Run:
    python scripts/test_extract_json_result.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner_adapters.base import extract_json_result  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture: reconstructed from the `result` field of
# tmp/work-order-runs/ec326936-0230-4a38-8a7a-4a2f80b1b627/execute_output.log
# (wrapper["result"] — the text that claude_code.py:298 passes to
# extract_json_result).  The key problematic fragment is the diff content
# string containing "{ children }: { children: React.ReactNode }" which
# confused the old brace-counter.
# ---------------------------------------------------------------------------
_RESULT_JSON = {
    "workOrderId": "ec326936-0230-4a38-8a7a-4a2f80b1b627",
    "finalStatus": "review_ready",
    "steps": [
        {
            "id": "4b2edc00-5d52-4456-8a42-89eabb18b369",
            "status": "completed",
            "outputSummary": 'Added translate="no" to the <html> tag and <meta name="google" content="notranslate" /> in layout.tsx.',
            "blockedReason": None,
        }
    ],
    "activityLogs": [
        {"level": "info", "eventType": "code_edit", "message": "Done.", "agentRunId": None}
    ],
    "artifacts": [
        {
            "type": "diff",
            "title": "layout.tsx — translate=no + notranslate meta",
            # This line is the regression: { } inside a string value broke
            # the old brace-counting scanner.
            "content": (
                "--- a/frontend/app/layout.tsx\n"
                "+++ b/frontend/app/layout.tsx\n"
                "@@ -16,7 +16,10 @@ export const viewport: Viewport = {\n"
                'export default function RootLayout({ children }: { children: React.ReactNode }) {\n'
                "  return (\n"
                '-    <html lang="en" className="dark">\n'
                '+    <html lang="en" className="dark" translate="no">\n'
            ),
        }
    ],
    "reviewPackage": {
        "summary": 'Added translate="no" to the root <html> element.',
        "filesChanged": ["frontend/app/layout.tsx"],
        "testsRun": ["next lint (ESLint)", "tsc --noEmit"],
        "risks": [],
        "openQuestions": [],
        "needsHumanReview": True,
        "recommendedNextStep": "Merge PR, then verify in Chrome.",
        "verdict": "ready_for_review",
    },
}

# The full text that extract_json_result() receives: prose + ```json fence
EC326936_RESULT_FIELD = (
    "Both lint and type-check pass cleanly. Here is the final result JSON:\n\n"
    "```json\n"
    + json.dumps(_RESULT_JSON, indent=2, ensure_ascii=False)
    + "\n```\n"
)


class ExtractJsonResultCodeBlockTests(unittest.TestCase):
    """Strategy 1: JSON embedded in a ```json...``` code block."""

    def test_ec326936_fixture_extracted_correctly(self):
        """The real-world failure case: diff content with { } in strings
        inside a ```json block — must be recognised, not return None."""
        result = extract_json_result(EC326936_RESULT_FIELD)
        self.assertIsNotNone(result, "expected a result dict, got None")
        self.assertEqual(result["workOrderId"], "ec326936-0230-4a38-8a7a-4a2f80b1b627")
        self.assertEqual(result["finalStatus"], "review_ready")

    def test_last_code_block_wins_when_multiple_present(self):
        """If the text has multiple ```json blocks, the LAST one is used."""
        first = json.dumps({"workOrderId": "first", "finalStatus": "failed"})
        second = json.dumps(_RESULT_JSON, ensure_ascii=False)
        text = f"```json\n{first}\n```\n\nsome text\n\n```json\n{second}\n```\n"
        result = extract_json_result(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["workOrderId"], "ec326936-0230-4a38-8a7a-4a2f80b1b627")


class ExtractJsonResultRawScanTests(unittest.TestCase):
    """Strategy 2: no code block — backward raw_decode scan."""

    def test_plain_json_with_braces_in_strings_extracted(self):
        """JSON without a code fence, but with { } inside string values,
        must still be found by the raw_decode fallback."""
        payload = {
            "workOrderId": "wo-plain",
            "finalStatus": "review_ready",
            "steps": [{"id": "s1", "status": "completed", "outputSummary": None, "blockedReason": None}],
            "activityLogs": [],
            "artifacts": [
                # { } inside a string — the old brace-counter breaks here
                {"type": "diff", "title": "t", "content": "fn foo({ x }: { x: number }) {}"}
            ],
            "reviewPackage": {
                "summary": "ok",
                "filesChanged": [],
                "testsRun": [],
                "risks": [],
                "openQuestions": [],
                "needsHumanReview": True,
                "recommendedNextStep": "review",
                "verdict": "ready_for_review",
            },
        }
        text = "Some preamble text.\n" + json.dumps(payload, ensure_ascii=False) + "\nSome trailing text."
        result = extract_json_result(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["workOrderId"], "wo-plain")
        self.assertEqual(result["finalStatus"], "review_ready")

    def test_no_valid_result_returns_none(self):
        """Text that contains no workOrderId/finalStatus dict → None."""
        self.assertIsNone(extract_json_result(""))
        self.assertIsNone(extract_json_result("no json here"))
        self.assertIsNone(extract_json_result('{"key": "value"}'))
        self.assertIsNone(extract_json_result("```json\n{\"unrelated\": 1}\n```"))
        self.assertIsNone(extract_json_result(
            '{"workOrderId": "wo-1"}'  # finalStatus missing
        ))


if __name__ == "__main__":
    unittest.main()
