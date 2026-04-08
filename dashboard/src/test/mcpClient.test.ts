import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { dashboardMcpClient } from "../lib/mcpClient";

const ENCODER = new TextEncoder();

function createOpenSseResponse(
  payload: unknown,
  init: {
    status?: number;
    headers?: Record<string, string>;
  } = {},
): Response {
  const body = `event: message\ndata: ${JSON.stringify(payload)}\n\n`;
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(ENCODER.encode(body));
      },
    }),
    {
      status: init.status ?? 200,
      headers: {
        "Content-Type": "text/event-stream",
        ...init.headers,
      },
    },
  );
}

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

  it("accepts an initialize response delivered as an open SSE stream", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        createOpenSseResponse(
          {
            jsonrpc: "2.0",
            id: "init-1",
            result: { protocolVersion: "2025-11-25" },
          },
          {
            headers: {
              "mcp-session-id": "session-sse-init",
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

    const timeout = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("timed out waiting for SSE initialize")), 150),
    );
    const payload = await Promise.race([
      dashboardMcpClient.callTool("query_dataset", {
        dataset_id: "sama-pos-weekly",
        filters: {},
        limit: 10,
      }),
      timeout,
    ]);

    expect(payload).toEqual({
      dataset_id: "sama-pos-weekly",
      status: "success",
    });
  });

  it("reads the first usable payload from an open SSE resource response", async () => {
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
              "mcp-session-id": "session-sse-resource",
            },
          },
        ),
      )
      .mockResolvedValueOnce(new Response("", { status: 202 }))
      .mockResolvedValueOnce(
        createOpenSseResponse({
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
      );

    vi.stubGlobal("fetch", fetchMock);

    const timeout = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("timed out waiting for SSE resource payload")), 150),
    );
    const payload = await Promise.race([
      dashboardMcpClient.readJsonResource("resource://catalog"),
      timeout,
    ]);

    expect(payload).toEqual({ dataset_count: 1, datasets: [] });
  });
});
