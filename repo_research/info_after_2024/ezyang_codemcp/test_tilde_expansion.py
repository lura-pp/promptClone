#!/usr/bin/env python3

"""End-to-end test for tilde expansion in paths."""

import unittest
from unittest.mock import patch

from codemcp.testing import MCPEndToEndTestCase


class TildeExpansionTest(MCPEndToEndTestCase):
    """Test that paths with tilde are properly expanded."""

    async def test_init_project_with_tilde(self):
        """Test that InitProject subtool can handle paths with tilde."""
        # Use a mocked expanduser to redirect any tilde path to self.temp_dir.name
        # This avoids issues with changing the current directory

        with patch("os.path.expanduser") as mock_expanduser:
            # Make expanduser replace any ~ with our temp directory path
            mock_expanduser.side_effect = lambda p: p.replace("~", self.temp_dir.name)

            async with self.create_client_session() as session:
                # Call InitProject with a path using tilde notation
                result_text = await self.call_tool_assert_success(
                    session,
                    "codemcp",
                    {
                        "subtool": "InitProject",
                        "path": "~/",  # Just a simple tilde path
                        "user_prompt": "Test with tilde path",
                        "subject_line": "feat: test tilde expansion",
                    },
                )

                # Verify the call was successful - the path was properly expanded
                # If the call succeeds, the path was properly expanded, otherwise
                # it would have failed to find the directory
                self.assertIn("Chat ID", result_text)


if __name__ == "__main__":
    unittest.main()
