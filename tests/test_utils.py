from unittest import TestCase
import meta_agent.utils as utils
from textwrap import dedent


class TestUtils(TestCase):
    def test_format_obj_into_text(self):
        testcases = [
            (
                "nameonly",
                "name",
                {
                    "name": "NAME",
                },
                """\
                # NAME
                ## name
                NAME""",
            ),
            (
                "attr-1",
                "name",
                {
                    "name": "NAME",
                    "attr1": "ATTR1",
                },
                """\
                # NAME
                ## attr1
                ATTR1

                ## name
                NAME""",
            ),
            (
                "codeblock",
                "name",
                {
                    "name": "NAME",
                    "code": dedent("""\
                    ```
                    CODE
                    ```
                    """),
                },
                """\
                # NAME
                ## code
                `````
                ```
                CODE
                ```
                `````


                ## name
                NAME""",
            ),
            (
                "markdown",
                "name",
                {
                    "name": "NAME",
                    "data": dedent("""\
                    # title
                    TITLE
                    """),
                },
                """\
                # NAME
                ## data
                `````
                # title
                TITLE
                `````


                ## name
                NAME""",
            ),
        ]
        for title, key, x, want in testcases:
            with self.subTest(title):
                got = utils.format_obj_into_text(key, x)
                w = dedent(want)
                self.assertEqual(w, got)
