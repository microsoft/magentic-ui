# Contributing to Magentic-UI

Thank you for your interest in contributing to Magentic-UI!
  
We welcome all contributions - whether it’s bug reports, feature requests, code, documentation, or helping others with their questions.

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).  
For more information, see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Contributor License Agreement (CLA)

Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution.  
For details, visit [https://opensource.microsoft.com/pdf/microsoft-contribution-license-agreement.pdf](https://opensource.microsoft.com/pdf/microsoft-contribution-license-agreement.pdf).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment).  
Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.


## How to Contribute

- **Find an Issue:**  
  - Browse [All Issues](https://github.com/microsoft/magentic-ui/issues).
  - Look for issues labeled with <span style="color:green"><strong>help-wanted</strong></span> as these are especially open for community contribution!
  - You can also help review [open PRs](https://github.com/microsoft/magentic-ui/pulls).

- **Pick Something to Work On:**  
  - See the checklist below for high-priority issues.
  - If you have an idea for a new feature or improvement, feel free to open a new issue for discussion.

- **Fork and Clone:**  
  - Fork the repository and clone it to your local machine.

- **Create a Branch:**  
  - Use a descriptive branch name (e.g., `fix/session-bug` or `feature/file-upload`).

- **Write Code and Tests:**  
  - Please include tests for new features or bug fixes. See the `tests` directory for examples.

- **Run Checks Locally:**  
  - Before submitting a PR, run:
    ```sh
    poe check
    ```

- **Submit a Pull Request:**  
  - Open a PR against the `main` branch.
  - Reference the issue number in your PR description (e.g., “Closes #123”).
  - The CLA bot will guide you if you need to sign the CLA.


## Community “Help Wanted” Issues

We use the green <span style="color:green"><strong>help-wanted</strong></span> label to highlight issues that are especially open for community contribution.  
Here are the top 10 issues you can help with right now:

- [ ] **Allow MAGUI to understand video and audio** ([#132](https://github.com/microsoft/magentic-ui/issues/132))
- [ ] **Enable arbitrary file upload in UI** ([#128](https://github.com/microsoft/magentic-ui/issues/128))
- [ ] **Add streaming of final answer and coder messages** ([#126](https://github.com/microsoft/magentic-ui/issues/126))
- [ ] **Add unit tests** ([#123](https://github.com/microsoft/magentic-ui/issues/123))
- [ ] **Allow websurfer to scroll inside containers** ([#124](https://github.com/microsoft/magentic-ui/issues/124))
- [ ] **Composing multiple plans** ([#129](https://github.com/microsoft/magentic-ui/issues/129))
- [ ] **Reduce latency** ([#131](https://github.com/microsoft/magentic-ui/issues/131))
- [ ] **Improve allowed list** ([#125](https://github.com/microsoft/magentic-ui/issues/125))
- [ ] **Add agent name to step in frontend** ([#110](https://github.com/microsoft/magentic-ui/issues/110))
- [ ] **Pass auth info for browser sessions** ([#120](https://github.com/microsoft/magentic-ui/issues/120))

See [all issues needing help](https://github.com/microsoft/magentic-ui/issues?q=is%3Aissue+is%3Aopen+label%3Ahelp-wanted).

## Reviewing Pull Requests

You can also help by reviewing [open PRs](https://github.com/microsoft/magentic-ui/pulls).

## Running Tests and Checks

All contributions must pass the continuous integration checks.  
You can run these checks locally before submitting a PR by running:

```bash
poe check
```

## Questions?

If you have any questions, open an issue or start a discussion.  
Thank you for helping make Magentic-UI better!
