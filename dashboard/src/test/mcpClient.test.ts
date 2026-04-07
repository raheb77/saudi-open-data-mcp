import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { dashboardMcpClient } from "../lib/mcpClient";

describe("dashboardMcpClient", () => {
  beforeEach(() => {
    dashboardMcpClient.resetSession();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    dashboardMcpClient.resetSession();
  });

  it("initializes a session once and calls a tool with session headers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            jsonrpc: "2.0",
            id: "init-1",
            result: { protocolVersion: "2025-11-25" },
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
              "mcp-session-id": "session-1",
            },
          },
        ),
      )
      .mockResolvedValueOnce(new Response("", { status: 202 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            jsonrpc: "2.0",
            id: "tool-1",
            result: {
              structuredContent: {
                dataset_id: "sama-pos-weekly",
                status: "success",
              },
            },
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
            },
          },
        ),
      );

    vi.stubGlobal("fetch", fetchMock);

    const payload = await dashboardMcpClient.callTool("query_dataset", {
      dataset_id: "sama-pos-weekly",
      filters: {},
      limit: 10,
    });

    expect(payload).toEqual({
      dataset_id: "sama-pos-weekly",
      status: "success",
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: "POST",
      headers: expect.objectContaining({
        "mcp-session-id": "session-1",
        "mcp-protocol-version": "2025-11-25",
      }),
    });
  });

  it("reads and parses JSON resources through MCP resources/read", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            jsonrpc: "2.0",
            id: "init-1",
            result: { protocolVersion: "2025-11-25" },
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
              "mcp-session-id": "session-2",
            },
          },
        ),
      )
      .mockResolvedValueOnce(new Response("", { status: 202 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            jsonrpc: "2.0",
            id: "resource-1",
            result: {
              contents: [
                {
                  uri: "resource://catalog",
                  text: JSON.stringify({
                    dataset_count: 1,
                    datasets: [],
                  }),
                },
              ],
            },
          }),
          {
            status: 200,
            headers: {
              "Content-Type": "application/json",
            },
          },
        ),
      );

    vi.stubGlobal("fetch", fetchMock);

    const payload = await dashboardMcpClient.readJsonResource("resource://catalog");
    expect(payload).toEqual({ dataset_count: 1, datasets: [] });
  });
});
