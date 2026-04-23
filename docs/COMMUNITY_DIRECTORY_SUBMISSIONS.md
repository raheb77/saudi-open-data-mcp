# Community Directory Submission Checklist

This document captures the final community directory submission package for `saudi-open-data-mcp`, the exact per-directory text variants, submission URLs, and the remaining manual steps.

It does not change any project logic.

If the matching package release is not live on PyPI yet, replace the PyPI link
in this checklist with the GitHub repository URL and avoid claiming a package
index install path externally until the release exists.

## Final Unified Submission Package

- Project title: Saudi Open Data MCP
- One-line short description: Governed MCP server for official Saudi open data with typed metadata and snapshot-backed tools.
- Positioning statement (47 words): Saudi Open Data MCP provides a governed interface to approved official Saudi datasets through explicit connectors, typed normalization, registry-backed metadata, and snapshot-backed querying. It is designed for internal or evaluator-controlled use where source boundaries, deterministic tool behavior, and transparent freshness metadata matter more than broad catalog coverage.
- Install snippet:

```bash
pip install saudi-open-data-mcp
saudi-open-data-mcp run-stdio
```

- GitHub link: https://github.com/raheb77/saudi-open-data-mcp
- Package index link, if the matching release is live: https://pypi.org/project/saudi-open-data-mcp/
- Screenshot path: `artifacts/mcp-inspector-connected-tools.png`
- Tags:
  - mcp
  - mcp-server
  - saudi-open-data
  - sama
  - fastmcp

## Exact Per-Directory Text

### Smithery

- Title: Saudi Open Data MCP
- Short description: Governed MCP server for official Saudi open data with typed metadata and snapshot-backed tools.
- Positioning statement: Saudi Open Data MCP provides a governed interface to approved official Saudi datasets through explicit connectors, typed normalization, registry-backed metadata, and snapshot-backed querying. It is designed for internal or evaluator-controlled use where source boundaries, deterministic tool behavior, and transparent freshness metadata matter more than broad catalog coverage.
- Install snippet:

```bash
pip install saudi-open-data-mcp
saudi-open-data-mcp run-stdio
```

- Primary link: use the PyPI project URL only when the matching release is live; otherwise use the GitHub repository URL
- Secondary link: https://github.com/raheb77/saudi-open-data-mcp
- Tags: mcp, mcp-server, saudi-open-data, sama, fastmcp

Checklist:
- [ ] Open Smithery submission page
- [ ] Log in
- [ ] Complete any maintainer or ownership verification
- [ ] Paste the text above into the relevant fields
- [ ] Upload screenshot if supported
- [ ] Review wording for consistency
- [ ] Submit manually

### Glama

- Title: Saudi Open Data MCP
- Short description: Governed MCP server for official Saudi open data with typed metadata and snapshot-backed tools.
- Positioning statement: Saudi Open Data MCP provides a governed interface to approved official Saudi datasets through explicit connectors, typed normalization, registry-backed metadata, and snapshot-backed querying. It is designed for internal or evaluator-controlled use where source boundaries, deterministic tool behavior, and transparent freshness metadata matter more than broad catalog coverage.
- Install snippet:

```bash
pip install saudi-open-data-mcp
saudi-open-data-mcp run-stdio
```

- Primary link: use the PyPI project URL only when the matching release is live; otherwise use the GitHub repository URL
- Secondary link: https://github.com/raheb77/saudi-open-data-mcp
- Tags: mcp, mcp-server, saudi-open-data, sama, fastmcp

Notes:
- Glama appears to be repo/discovery-oriented.
- If Glama only asks for a GitHub repository URL after sign-in, keep this wording as the canonical copy for any description or notes field.

Checklist:
- [ ] Open Glama registry page
- [ ] Click Add Server
- [ ] Sign up or sign in
- [ ] Complete CAPTCHA if required
- [ ] Provide repository and package details
- [ ] Paste the text above into any description fields
- [ ] Upload screenshot if supported
- [ ] Review wording for consistency
- [ ] Submit manually

### PulseMCP

- Title: Saudi Open Data MCP
- Short description: Governed MCP server for official Saudi open data with typed metadata and snapshot-backed tools.
- Positioning statement: Saudi Open Data MCP provides a governed interface to approved official Saudi datasets through explicit connectors, typed normalization, registry-backed metadata, and snapshot-backed querying. It is designed for internal or evaluator-controlled use where source boundaries, deterministic tool behavior, and transparent freshness metadata matter more than broad catalog coverage.
- Install snippet:

```bash
pip install saudi-open-data-mcp
saudi-open-data-mcp run-stdio
```

- Primary link: use the PyPI project URL only when the matching release is live; otherwise use the GitHub repository URL
- Secondary link: https://github.com/raheb77/saudi-open-data-mcp
- Tags: mcp, mcp-server, saudi-open-data, sama, fastmcp

Notes:
- PulseMCP returned `Access Denied` from the browser environment used during preparation.
- A public submission form URL could not be confirmed from this environment.

Checklist:
- [ ] Open PulseMCP from your own browser/network
- [ ] Find the actual submission flow or submission page
- [ ] Paste the text above into the relevant fields
- [ ] Upload screenshot if supported
- [ ] Review wording for consistency
- [ ] Submit manually

### mcp.so

- Title: Saudi Open Data MCP
- Short description: Governed MCP server for official Saudi open data with typed metadata and snapshot-backed tools.
- Positioning statement: Saudi Open Data MCP provides a governed interface to approved official Saudi datasets through explicit connectors, typed normalization, registry-backed metadata, and snapshot-backed querying. It is designed for internal or evaluator-controlled use where source boundaries, deterministic tool behavior, and transparent freshness metadata matter more than broad catalog coverage.
- Install snippet:

```bash
pip install saudi-open-data-mcp
saudi-open-data-mcp run-stdio
```

- Primary link: use the PyPI project URL only when the matching release is live; otherwise use the GitHub repository URL
- Secondary link: https://github.com/raheb77/saudi-open-data-mcp
- Tags: mcp, mcp-server, saudi-open-data, sama, fastmcp
- Server config entered on the form:

```json
{
  "mcpServers": {
    "saudi-open-data-mcp": {
      "command": "saudi-open-data-mcp",
      "args": ["run-stdio"]
    }
  }
}
```

Checklist:
- [ ] Open the mcp.so submission page
- [ ] Verify the prefilled fields match this document
- [ ] Review the JSON server config
- [ ] Submit manually

## Submission URLs

- Smithery: https://smithery.ai/servers/new
- Glama: https://glama.ai/mcp/servers
- PulseMCP: https://pulsemcp.com/
- PulseMCP attempted submit URL during preparation: https://pulsemcp.com/submit
- mcp.so: https://mcp.so/submit

## Browser Progress Already Completed

### Smithery
- Reached the official new-server route
- Hit the authentication gate
- Stopped before login

### Glama
- Opened the MCP servers registry
- Triggered the Add Server flow
- Reached sign-up gate with CAPTCHA
- Stopped before sign-up, login, or CAPTCHA completion

### PulseMCP
- Attempted public site access
- Browser received `Access Denied`
- No usable submission form could be reached from the preparation environment

### mcp.so
- Opened the submission form
- Filled these fields during preparation:
  - Name: Saudi Open Data MCP
  - URL: https://github.com/raheb77/saudi-open-data-mcp
  - Server Config: the JSON block above
- Stopped before clicking Submit

## Remaining Manual Steps Summary

- [ ] Smithery: log in, verify ownership if required, paste copy, upload screenshot if supported, submit
- [ ] Glama: sign in or sign up, complete CAPTCHA, add the server, paste copy where needed, upload screenshot if supported, submit
- [ ] PulseMCP: open from your own network, locate the real submission flow, paste copy, upload screenshot if supported, submit
- [ ] mcp.so: review the filled form and click Submit

## Consistency Rules To Preserve

- Prefer the package-index link plus GitHub only when the matching package release is live; otherwise prefer GitHub
- Keep wording technically serious and non-hypey
- Do not add unsupported claims
- Keep the description and positioning statement consistent across all directories
- Use the screenshot at `artifacts/mcp-inspector-connected-tools.png`
