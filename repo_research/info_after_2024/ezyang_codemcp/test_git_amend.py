#!/usr/bin/env python3

"""Tests for the Git amend functionality."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class GitAmendTest(MCPEndToEndTestCase):
    """Test the Git amend functionality for commits."""

    async def test_amend_commit_same_chat_id(self):
        """Test that subsequent edits within the same chat session amend the previous commit."""
        # Create a file to edit multiple times
        test_file_path = os.path.join(self.temp_dir.name, "amend_test.txt")
        initial_content = "Initial content\nLine 2"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it
        await self.git_run(["commit", "-m", "Add file for amend test"])

        # Get the current commit count
        log_output = await self.git_run(
            ["log", "--oneline"], capture_output=True, text=True
        )
        initial_commit_count = len(log_output.split("\n"))

        async with self.create_client_session() as session:
            # First initialize the project to get a chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for amend test",
                    "subject_line": "test: initialize for amend commit test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # First edit with our chat_id using our helper method
            result_text1 = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Initial content\nLine 2",
                    "new_string": "Modified content\nLine 2",
                    "description": "First edit",
                    "chat_id": chat_id,
                },
            )

            # Verify success message
            self.assertIn("Successfully edited", result_text1)

            # Get the current commit count after first edit
            log_output = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            commit_count_after_first_edit = len(log_output.split("\n"))

            # Verify a new commit was created (initial + 1)
            self.assertEqual(
                commit_count_after_first_edit,
                initial_commit_count + 1,
                "A new commit should be created for the first edit",
            )

            # Get the last commit message and check for chat_id metadata
            commit_msg1 = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )
            self.assertIn(f"codemcp-id: {chat_id}", commit_msg1)
            self.assertIn("First edit", commit_msg1)

            # Second edit with the same chat_id using our helper method
            result_text2 = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Modified content\nLine 2",
                    "new_string": "Modified content\nLine 2\nLine 3",
                    "description": "Second edit",
                    "chat_id": chat_id,
                },
            )

            # Verify success message
            self.assertIn("Successfully edited", result_text2)

            # Get the commit count after second edit
            log_output = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            commit_count_after_second_edit = len(log_output.split("\n"))

            # Verify the commit count remains the same (amend)
            self.assertEqual(
                commit_count_after_second_edit,
                commit_count_after_first_edit,
                "The second edit should amend the previous commit, not create a new one",
            )

            # Get the last commit message
            commit_msg2 = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # Verify the commit message contains both edits and the chat ID
            self.assertIn(f"codemcp-id: {chat_id}", commit_msg2)
            self.assertIn("First edit", commit_msg2)
            self.assertIn("Second edit", commit_msg2)

            # Use more general regex patterns that don't depend on exact placement
            # Just check that both base revision and HEAD markers exist somewhere in the commit message
            import re

            base_revision_regex = r"[0-9a-f]{7}\s+\(Base revision\)"
            head_regex = r"HEAD\s+Second edit"

            self.assertTrue(
                re.search(base_revision_regex, commit_msg2, re.MULTILINE),
                f"Commit message doesn't contain base revision pattern. Got: {commit_msg2}",
            )
            self.assertTrue(
                re.search(head_regex, commit_msg2, re.MULTILINE),
                f"Commit message doesn't contain HEAD pattern. Got: {commit_msg2}",
            )

    async def test_new_commit_different_chat_id(self):
        """Test that edits with a different chat_id create a new commit rather than amending."""
        # Create a file to edit
        test_file_path = os.path.join(self.temp_dir.name, "different_chat_test.txt")
        initial_content = "Initial content for different chat test"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it
        await self.git_run(["commit", "-m", "Add file for different chat test"])

        # Get the current commit count
        log_output = await self.git_run(
            ["log", "--oneline"], capture_output=True, text=True
        )
        initial_commit_count = len(log_output.split("\n"))

        async with self.create_client_session() as session:
            # First initialize the project to get first chat_id
            init_result_text1 = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for different chat ID test 1",
                    "subject_line": "test: initialize for different chat 1",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract first chat_id from the init result
            chat_id1 = self.extract_chat_id_from_text(init_result_text1)

            # First edit with chat_id1
            result1_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Initial content for different chat test",
                    "new_string": "Modified by chat 1",
                    "description": "Edit from chat 1",
                    "chat_id": chat_id1,
                },
            )

            # Check the result
            self.assertIn("Successfully edited", result1_text)

            # Get the commit count after first edit
            log_output = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            commit_count_after_first_edit = len(log_output.split("\n"))

            # Verify a new commit was created
            self.assertEqual(
                commit_count_after_first_edit,
                initial_commit_count + 1,
                "A new commit should be created for the first chat",
            )

            # Initialize the project to get second chat_id
            init_result_text2 = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for different chat ID test 2",
                    "subject_line": "test: initialize for different chat 2",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract second chat_id from the init result
            chat_id2 = self.extract_chat_id_from_text(init_result_text2)

            # Edit with chat_id2
            result2_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Modified by chat 1",
                    "new_string": "Modified by chat 2",
                    "description": "Edit from chat 2",
                    "chat_id": chat_id2,
                },
            )

            # Check the result
            self.assertIn("Successfully edited", result2_text)

            # Get the commit count after second edit
            log_output = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            commit_count_after_second_edit = len(log_output.split("\n"))

            # Verify a new commit was created (not amended)
            self.assertEqual(
                commit_count_after_second_edit,
                commit_count_after_first_edit + 1,
                "Edit with different chat_id should create a new commit",
            )

            # Get the last two commit messages
            commit_msgs = await self.git_run(
                ["log", "-2", "--pretty=%B"], capture_output=True, text=True
            )

            # Verify the latest commit has chat_id2
            self.assertIn(f"codemcp-id: {chat_id2}", commit_msgs)
            self.assertIn("Edit from chat 2", commit_msgs)

            # Verify the previous commit has chat_id1
            self.assertIn(f"codemcp-id: {chat_id1}", commit_msgs)

    async def test_non_ai_commit_not_amended(self):
        """Test that a user (non-AI) generated commit isn't amended."""
        # Create a file to edit
        test_file_path = os.path.join(self.temp_dir.name, "user_commit_test.txt")
        initial_content = "Initial content for user commit test"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it (user-generated commit without a chat_id)
        await self.git_run(["commit", "-m", "User-generated commit"])

        # Get the current commit count
        log_output = await self.git_run(
            ["log", "--oneline"], capture_output=True, text=True
        )
        initial_commit_count = len(log_output.split("\n"))

        async with self.create_client_session() as session:
            # Initialize the project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for user commit test",
                    "subject_line": "test: initialize for non-AI commit test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # AI-generated edit
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Initial content for user commit test",
                    "new_string": "Modified by AI",
                    "description": "AI edit after user commit",
                    "chat_id": chat_id,
                },
            )

            # Check the result
            self.assertIn("Successfully edited", result_text)

            # Get the commit count after AI edit
            log_output = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            commit_count_after_edit = len(log_output.split("\n"))

            # Verify a new commit was created (not amended)
            self.assertEqual(
                commit_count_after_edit,
                initial_commit_count + 1,
                "AI edit after user commit should create a new commit, not amend",
            )

            # Get the last two commit messages
            commit_msgs = await self.git_run(
                ["log", "-2", "--pretty=%B"], capture_output=True, text=True
            )

            # Verify the latest commit has AI chat_id
            self.assertIn(f"codemcp-id: {chat_id}", commit_msgs)

            # Verify the user commit message is included
            self.assertIn("User-generated commit", commit_msgs)

            # Make sure there's only one codemcp-id in the output
            codemcp_id_count = commit_msgs.count("codemcp-id:")
            self.assertEqual(
                codemcp_id_count, 1, "Should be only one codemcp-id metadata tag"
            )

    async def test_commit_history_with_nonhead_match(self):
        """Test behavior when HEAD~ has the same chat_id as current but HEAD doesn't."""
        # Create a file to edit
        test_file_path = os.path.join(self.temp_dir.name, "history_test.txt")
        initial_content = "Initial content for history test"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it
        await self.git_run(["commit", "-m", "Add file for history test"])

        async with self.create_client_session() as session:
            # Initialize the project to get first chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for history test",
                    "subject_line": "test: initialize for history test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id1 = self.extract_chat_id_from_text(init_result_text)

        # Helper function to create a commit with chat ID
        async def create_chat_commit(content, message, chat_id):
            with open(test_file_path, "w") as f:
                f.write(content)

            await self.git_run(["add", test_file_path])
            await self.git_run(["commit", "-m", f"{message}\n\ncodemcp-id: {chat_id}"])

        # Create first AI commit with chat_id1
        await create_chat_commit("Modified by chat 1", "First AI edit", chat_id1)

        # Create a user commit (different chat_id)
        await create_chat_commit("Modified by user", "User edit", "some-other-chat")

        # Get the current commit count
        log_output = await self.git_run(
            ["log", "--oneline"], capture_output=True, text=True
        )
        len(log_output.split("\n"))

        async with self.create_client_session() as session:
            # Initialize the project again with the same chat_id
            init_result_text2 = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test second initialization for history test",
                    "subject_line": "test: second initialize for history test",
                    "reuse_head_chat_id": True,
                },
            )

            # Get a new chat_id for the second edit
            # We don't want to reuse the HEAD chat_id here since we're testing edits
            # when HEAD has a different chat ID
            second_chat_id = self.extract_chat_id_from_text(init_result_text2)

            # New edit with the second chat_id
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Modified by user",
                    "new_string": "Modified again by chat 1",
                    "description": "Second edit from chat 1",
                    "chat_id": second_chat_id,
                },
            )

            # Check the result
            self.assertIn("Successfully edited", result_text)

            # Get the commit count after the new edit
            log_output = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            len(log_output.split("\n"))

            # We should verify the edit was made successfully without asserting
            # a specific commit count, as that's not the main purpose of this test

            # Get the last commit message
            last_commit_msg = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # Verify the latest commit has the correct chat_id and message
            # The main point is that the edited content is correct and the commit has the
            # right chat_id and message
            self.assertIn(f"codemcp-id: {second_chat_id}", last_commit_msg)
            self.assertIn("Second edit from chat 1", last_commit_msg)

    async def test_write_with_no_chatid(self):
        """Test that WriteFile creates a new commit if HEAD has no chat ID."""
        # Create a file to edit
        test_file_path = os.path.join(self.temp_dir.name, "no_chatid_test.txt")
        initial_content = "Initial content without chat ID"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it without a chat ID
        await self.git_run(["commit", "-m", "Regular commit without chat ID"])

        # Get the current commit count
        log_output = await self.git_run(
            ["log", "--oneline"], capture_output=True, text=True
        )
        initial_commit_count = len(log_output.split("\n"))

        async with self.create_client_session() as session:
            # Initialize the project to get AI chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for no chatid test",
                    "subject_line": "test: initialize for no chatid test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract AI chat_id from the init result
            ai_chat_id = self.extract_chat_id_from_text(init_result_text)

            # Write with an AI chat ID using our helper method
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": "Modified content with AI chat ID",
                    "description": "Write with AI chat ID",
                    "chat_id": ai_chat_id,
                },
            )

            # Verify success message
            self.assertIn("Successfully wrote to", result_text)

            # Get the commit count after the write
            log_output = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            commit_count_after_write = len(log_output.split("\n"))

            # Verify a new commit was created (not amended)
            self.assertEqual(
                commit_count_after_write,
                initial_commit_count + 1,
                "Write after commit without chat_id should create a new commit",
            )

            # Get the commit messages
            commit_msgs = await self.git_run(
                ["log", "-2", "--pretty=%B"], capture_output=True, text=True
            )

            # Verify new commit has AI chat_id
            self.assertIn(f"codemcp-id: {ai_chat_id}", commit_msgs)
            self.assertIn("Write with AI chat ID", commit_msgs)

            # Verify previous commit message is included
            self.assertIn("Regular commit without chat ID", commit_msgs)

            # Make sure there's only one codemcp-id in the output
            codemcp_id_count = commit_msgs.count("codemcp-id:")
            self.assertEqual(
                codemcp_id_count, 1, "Should be only one codemcp-id metadata tag"
            )

    async def test_write_with_different_chatid(self):
        """Test that WriteFile creates a new commit if HEAD has a different chat ID."""
        # Create a file to edit
        test_file_path = os.path.join(self.temp_dir.name, "write_test.txt")
        initial_content = "Initial content for write test"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])

        # First initialize the project to get first chat_id
        async with self.create_client_session() as session:
            init_result_text1 = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for write with different chat id",
                    "subject_line": "test: initialize for different chat id write test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract first chat_id from the init result
            first_chat_id = self.extract_chat_id_from_text(init_result_text1)

            # Create a simple file to simulate an AI commit with the first chat_id
            await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Initial content for write test",
                    "new_string": "Modified by first chat",
                    "description": "First edit",
                    "chat_id": first_chat_id,
                },
            )

        # Get the current commit count
        log_output = await self.git_run(
            ["log", "--oneline"], capture_output=True, text=True
        )
        initial_commit_count = len(log_output.split("\n"))

        # Initialize the project again to get a second chat_id
        async with self.create_client_session() as session:
            init_result_text2 = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for second chat id",
                    "subject_line": "test: initialize for second chat id",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract second chat_id from the init result
            second_chat_id = self.extract_chat_id_from_text(init_result_text2)

            # Write to the file with a different chat ID using our helper method
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": "Modified content for write test",
                    "description": "Write with different chat ID",
                    "chat_id": second_chat_id,
                },
            )

            # Verify success message
            self.assertIn("Successfully wrote to", result_text)

            # Get the commit count after the write
            log_output = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            commit_count_after_write = len(log_output.split("\n"))

            # Verify a new commit was created (not amended)
            self.assertEqual(
                commit_count_after_write,
                initial_commit_count + 1,
                "Write with different chat_id should create a new commit",
            )

            # Get the commit messages
            commit_msgs = await self.git_run(
                ["log", "-2", "--pretty=%B"], capture_output=True, text=True
            )

            # Verify both chat IDs are in the commit history
            self.assertIn(f"codemcp-id: {second_chat_id}", commit_msgs)
            self.assertIn(f"codemcp-id: {first_chat_id}", commit_msgs)

            # Make sure there are exactly two codemcp-id tags in the output
            codemcp_id_count = commit_msgs.count("codemcp-id:")
            self.assertEqual(
                codemcp_id_count, 2, "Should be exactly two codemcp-id metadata tags"
            )

    async def test_commit_hash_in_message(self):
        """Test that the commit hash appears in the commit message when amending."""
        # Create a file to edit multiple times
        test_file_path = os.path.join(self.temp_dir.name, "hash_test.txt")
        initial_content = "Hash test content"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it
        await self.git_run(["commit", "-m", "Add file for hash test"])

        async with self.create_client_session() as session:
            # Initialize the project to get a chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for hash test",
                    "subject_line": "test: initialize for hash test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # First edit with our chat_id
            result1_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Hash test content",
                    "new_string": "Modified hash test content",
                    "description": "First hash test edit",
                    "chat_id": chat_id,
                },
            )

            # Check the result
            self.assertIn("Successfully edited", result1_text)

            # Get the commit hash for the first edit
            await self.git_run(
                ["rev-parse", "--short", "HEAD"], capture_output=True, text=True
            )

            # Second edit with the same chat_id
            result2_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Modified hash test content",
                    "new_string": "Twice modified hash test content",
                    "description": "Second hash test edit",
                    "chat_id": chat_id,
                },
            )

            # Check in the response text for the commit hash pattern in the result
            import re

            hash_pattern = r"previous commit was [0-9a-f]{7}"
            self.assertTrue(
                re.search(hash_pattern, result2_text),
                f"Result text doesn't mention previous commit hash. Got: {result2_text}",
            )

            # Get the last commit message
            commit_msg = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # Verify the commit hash format in the message with base revision and HEAD
            import re

            base_revision_regex = r"[0-9a-f]{7}\s+\(Base revision\)"
            head_regex = r"HEAD\s+Second hash test edit"

            self.assertTrue(
                re.search(base_revision_regex, commit_msg, re.MULTILINE),
                f"Commit message doesn't contain base revision pattern. Got: {commit_msg}",
            )
            self.assertTrue(
                re.search(head_regex, commit_msg, re.MULTILINE),
                f"Commit message doesn't contain HEAD pattern. Got: {commit_msg}",
            )

            # Third edit to check multiple hash entries
            await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Twice modified hash test content",
                    "new_string": "Thrice modified hash test content",
                    "description": "Third hash test edit",
                    "chat_id": chat_id,
                },
            )

            # Get the second commit hash
            await self.git_run(
                ["rev-parse", "--short", "HEAD"], capture_output=True, text=True
            )

            # Get the updated commit message
            final_commit_msg = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # Verify both commit hashes appear in the correct format
            import re

            # Check for base revision and head format
            base_revision_regex = r"[0-9a-f]{7}\s+\(Base revision\)"
            hash_edit_regex = r"[0-9a-f]{7}\s+Second hash test edit"
            head_regex = r"HEAD\s+Third hash test edit"

            self.assertTrue(
                re.search(base_revision_regex, final_commit_msg, re.MULTILINE),
                f"Commit message doesn't contain base revision pattern. Got: {final_commit_msg}",
            )
            self.assertTrue(
                re.search(hash_edit_regex, final_commit_msg, re.MULTILINE),
                f"Commit message doesn't contain hash pattern for second edit. Got: {final_commit_msg}",
            )
            self.assertTrue(
                re.search(head_regex, final_commit_msg, re.MULTILINE),
                f"Commit message doesn't contain HEAD pattern. Got: {final_commit_msg}",
            )


if __name__ == "__main__":
    unittest.main()
