const MCP_ENDPOINT = "/mcp";
const READINESS_ENDPOINT = "/startupz";
const CLIENT_INFO = {
  name: "saudi-open-data-mcp-dashboard",
  version: "0.1.0",
} as const;
const LATEST_PROTOCOL_VERSION = "2025-11-25";

type JsonRpcId = string;

interface JsonRpcSuccess<T> {
  jsonrpc: "2.0";
  id?: JsonRpcId | number | null;
  result: T;
}

interface JsonRpcFailure {
  jsonrpc: "2.0";
  id?: JsonRpcId | number | null;
  error: {
    code: number;
    message: string;
    data?: unknown;
  };
}

interface McpSession {
  sessionId: string;
  protocolVersion: string;
}

interface ToolCallResult {
  structuredContent?: unknown;
  content?: Array<{ type?: string; text?: string }>;
  isError?: boolean;
}

interface ResourceReadResult {
  contents?: Array<{ text?: string }>;
}

export class DashboardApiError extends Error {
  kind: "unauthorized" | "network" | "protocol" | "validation";
  stage: string;
  status?: number;

  constructor(
    kind: DashboardApiError["kind"],
    stage: string,
    message: string,
    options: {
      status?: number;
      cause?: unknown;
    } = {},
  ) {
    super(message);
    this.name = "DashboardApiError";
    this.kind = kind;
    this.stage = stage;
    this.status = options.status;
    if (options.cause !== undefined) {
      this.cause = options.cause;
    }
  }
}

export function asDashboardApiError(
  error: unknown,
  stage: string,
  fallbackMessage: string,
): DashboardApiError {
  if (error instanceof DashboardApiError) {
    return error;
  }
  return new DashboardApiError(
    "validation",
    stage,
    error instanceof Error ? error.message : fallbackMessage,
    { cause: error },
  );
}

function nextRequestId(): JsonRpcId {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isJsonRpcFailure(value: unknown): value is JsonRpcFailure {
  return isRecord(value) && isRecord(value.error) && typeof value.error.message === "string";
}

function isJsonRpcSuccess<T>(value: unknown): value is JsonRpcSuccess<T> {
  return isRecord(value) && "result" in value;
}

function isUnauthorizedStatus(status: number): boolean {
  return status === 401 || status === 403;
}

function isEventStreamContentType(contentType: string | null): boolean {
  return (contentType ?? "").toLowerCase().startsWith("text/event-stream");
}

function isSessionLifecycleMessage(message: string): boolean {
  const normalized = message.toLowerCase();
  return normalized.includes("missing session") || normalized.includes("session");
}

async function parseJsonResponse(
  response: Response,
  stage: string,
): Promise<unknown> {
  try {
    return await response.json();
  } catch (error) {
    throw new DashboardApiError(
      "protocol",
      stage,
      "استجابة MCP لم تكن JSON قابلة للقراءة.",
      { status: response.status, cause: error },
    );
  }
}

interface ParsedSseEvent {
  event: string;
  data: string;
}

async function parseMcpResponsePayload(
  response: Response,
  stage: string,
): Promise<unknown> {
  if (isEventStreamContentType(response.headers.get("content-type"))) {
    return parseSseResponse(response, stage);
  }
  return parseJsonResponse(response, stage);
}

async function parseSseResponse(
  response: Response,
  stage: string,
): Promise<unknown> {
  if (!response.body) {
    throw new DashboardApiError(
      "protocol",
      stage,
      "استجابة SSE الحية لا تحتوي على body قابل للقراءة.",
      { status: response.status },
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (value) {
        buffer += decoder.decode(value, { stream: !done });
      }
      if (done) {
        buffer += decoder.decode();
      }

      let boundary = findSseEventBoundary(buffer);
      while (boundary) {
        const rawEvent = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary.length);
        const payload = parseSseEventPayload(rawEvent, stage, response.status);
        if (payload !== undefined) {
          return payload;
        }
        boundary = findSseEventBoundary(buffer);
      }

      if (done) {
        break;
      }
    }

    const finalPayload = parseSseEventPayload(buffer, stage, response.status);
    if (finalPayload !== undefined) {
      return finalPayload;
    }
  } catch (error) {
    if (error instanceof DashboardApiError) {
      throw error;
    }
    throw new DashboardApiError(
      "protocol",
      stage,
      "تعذّر قراءة استجابة SSE من مسار MCP الحي.",
      { status: response.status, cause: error },
    );
  } finally {
    try {
      await reader.cancel();
    } catch {
      // Reader may already be closed after the server ends the stream.
    }
  }

  throw new DashboardApiError(
    "protocol",
    stage,
    "انتهى تدفق SSE قبل وصول payload MCP قابل للاستخدام.",
    { status: response.status },
  );
}

function findSseEventBoundary(
  buffer: string,
): { index: number; length: number } | null {
  const separators = ["\r\n\r\n", "\n\n", "\r\r"];
  let earliest: { index: number; length: number } | null = null;

  for (const separator of separators) {
    const index = buffer.indexOf(separator);
    if (index === -1) {
      continue;
    }
    if (!earliest || index < earliest.index) {
      earliest = { index, length: separator.length };
    }
  }

  return earliest;
}

function parseSseEventPayload(
  rawEvent: string,
  stage: string,
  status: number,
): unknown | undefined {
  const event = parseSseEvent(rawEvent);
  if (!event || event.event !== "message" || !event.data.trim()) {
    return undefined;
  }

  try {
    return JSON.parse(event.data);
  } catch (error) {
    throw new DashboardApiError(
      "protocol",
      stage,
      "بيانات حدث SSE من مسار MCP ليست JSON صالحًا.",
      { status, cause: error },
    );
  }
}

function parseSseEvent(rawEvent: string): ParsedSseEvent | null {
  if (!rawEvent.trim()) {
    return null;
  }

  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of rawEvent.split(/\r\n|\n|\r/)) {
    if (!line || line.startsWith(":")) {
      continue;
    }

    const separatorIndex = line.indexOf(":");
    const field =
      separatorIndex === -1 ? line : line.slice(0, separatorIndex).trim();
    let value =
      separatorIndex === -1 ? "" : line.slice(separatorIndex + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }

    if (field === "event") {
      eventName = value || "message";
      continue;
    }

    if (field === "data") {
      dataLines.push(value);
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  return {
    event: eventName,
    data: dataLines.join("\n"),
  };
}

class McpHttpClient {
  private sessionPromise: Promise<McpSession> | null = null;

  async callTool(
    name: string,
    args: Record<string, unknown>,
    signal?: AbortSignal,
  ): Promise<unknown> {
    const result = await this.request<ToolCallResult>(
      "tools/call",
      {
        name,
        arguments: args,
      },
      "tool_call",
      signal,
    );
    if (result.structuredContent !== undefined) {
      return result.structuredContent;
    }
    const text = result.content?.find((entry) => entry.type === "text")?.text;
    if (!text) {
      throw new DashboardApiError(
        "protocol",
        "tool_response",
        "استجابة الأداة الحية لا تحتوي على structuredContent قابل للاستخدام.",
      );
    }
    try {
      return JSON.parse(text);
    } catch (error) {
      throw new DashboardApiError(
        "protocol",
        "tool_response",
        "نص استجابة الأداة ليس JSON صالحًا.",
        { cause: error },
      );
    }
  }

  async readJsonResource(uri: string, signal?: AbortSignal): Promise<unknown> {
    const result = await this.request<ResourceReadResult>(
      "resources/read",
      { uri },
      "resource_read",
      signal,
    );
    const text = result.contents?.[0]?.text;
    if (!text) {
      throw new DashboardApiError(
        "protocol",
        "resource_response",
        "استجابة المورد الحي لا تحتوي على نص JSON.",
      );
    }
    try {
      return JSON.parse(text);
    } catch (error) {
      throw new DashboardApiError(
        "protocol",
        "resource_response",
        "نص المورد ليس JSON صالحًا.",
        { cause: error },
      );
    }
  }

  async getReadiness(signal?: AbortSignal): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(READINESS_ENDPOINT, {
        method: "GET",
        signal,
        headers: {
          Accept: "application/json",
        },
      });
    } catch (error) {
      throw new DashboardApiError(
        "network",
        "readiness_fetch",
        "تعذّر الاتصال بمسار الجاهزية الحي.",
        { cause: error },
      );
    }

    if (isUnauthorizedStatus(response.status)) {
      throw new DashboardApiError(
        "unauthorized",
        "readiness_fetch",
        "الواجهة غير مخوّلة للوصول إلى مسار الجاهزية.",
        { status: response.status },
      );
    }

    if (!response.ok) {
      throw new DashboardApiError(
        "protocol",
        "readiness_fetch",
        "أعاد مسار الجاهزية استجابة غير متوقعة.",
        { status: response.status },
      );
    }

    return parseJsonResponse(response, "readiness_parse");
  }

  private async request<T>(
    method: string,
    params: Record<string, unknown>,
    stage: string,
    signal?: AbortSignal,
    canRetrySession = true,
  ): Promise<T> {
    const session = await this.initializeSession();
    let response: Response;
    try {
      response = await fetch(MCP_ENDPOINT, {
        method: "POST",
        signal,
        headers: {
          Accept: "application/json, text/event-stream",
          "Content-Type": "application/json",
          "mcp-session-id": session.sessionId,
          "mcp-protocol-version": session.protocolVersion,
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: nextRequestId(),
          method,
          params,
        }),
      });
    } catch (error) {
      throw new DashboardApiError(
        "network",
        stage,
        "تعذّر الاتصال بمسار MCP الحي.",
        { cause: error },
      );
    }

    if (isUnauthorizedStatus(response.status)) {
      throw new DashboardApiError(
        "unauthorized",
        stage,
        "الواجهة غير مخوّلة للوصول إلى مسار MCP الحي.",
        { status: response.status },
      );
    }

    const payload = await parseMcpResponsePayload(response, stage);
    if (isJsonRpcFailure(payload)) {
      if (canRetrySession && isSessionLifecycleMessage(payload.error.message)) {
        this.resetSession();
        return this.request<T>(method, params, stage, signal, false);
      }
      throw new DashboardApiError(
        "protocol",
        stage,
        payload.error.message,
        { status: response.status, cause: payload.error.data },
      );
    }

    if (!isJsonRpcSuccess<T>(payload)) {
      throw new DashboardApiError(
        "protocol",
        stage,
        "استجابة JSON-RPC الحية لا تحتوي على result.",
        { status: response.status },
      );
    }

    return payload.result;
  }

  private async initializeSession(): Promise<McpSession> {
    if (this.sessionPromise) {
      return this.sessionPromise;
    }
    this.sessionPromise = this.startSession().catch((error) => {
      this.sessionPromise = null;
      throw error;
    });
    return this.sessionPromise;
  }

  private async startSession(): Promise<McpSession> {
    let response: Response;
    try {
      response = await fetch(MCP_ENDPOINT, {
        method: "POST",
        headers: {
          Accept: "application/json, text/event-stream",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: nextRequestId(),
          method: "initialize",
          params: {
            protocolVersion: LATEST_PROTOCOL_VERSION,
            capabilities: {},
            clientInfo: CLIENT_INFO,
          },
        }),
      });
    } catch (error) {
      throw new DashboardApiError(
        "network",
        "mcp_initialize",
        "تعذّر إنشاء جلسة MCP حية.",
        { cause: error },
      );
    }

    if (isUnauthorizedStatus(response.status)) {
      throw new DashboardApiError(
        "unauthorized",
        "mcp_initialize",
        "الواجهة غير مخوّلة لبدء جلسة MCP حية.",
        { status: response.status },
      );
    }

    const payload = await parseMcpResponsePayload(response, "mcp_initialize");
    if (isJsonRpcFailure(payload)) {
      throw new DashboardApiError(
        "protocol",
        "mcp_initialize",
        payload.error.message,
        { status: response.status, cause: payload.error.data },
      );
    }
    if (!isJsonRpcSuccess<{ protocolVersion?: unknown }>(payload)) {
      throw new DashboardApiError(
        "protocol",
        "mcp_initialize",
        "استجابة initialize لا تحتوي على result صالح.",
        { status: response.status },
      );
    }

    const sessionId = response.headers.get("mcp-session-id");
    if (!sessionId) {
      throw new DashboardApiError(
        "protocol",
        "mcp_initialize",
        "الخادم الحي لم يُعد mcp-session-id بعد initialize.",
        { status: response.status },
      );
    }

    const protocolVersion =
      typeof payload.result.protocolVersion === "string"
        ? payload.result.protocolVersion
        : LATEST_PROTOCOL_VERSION;

    await this.sendInitializedNotification(sessionId, protocolVersion);
    return {
      sessionId,
      protocolVersion,
    };
  }

  private async sendInitializedNotification(
    sessionId: string,
    protocolVersion: string,
  ): Promise<void> {
    let response: Response;
    try {
      response = await fetch(MCP_ENDPOINT, {
        method: "POST",
        headers: {
          Accept: "application/json, text/event-stream",
          "Content-Type": "application/json",
          "mcp-session-id": sessionId,
          "mcp-protocol-version": protocolVersion,
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: "notifications/initialized",
        }),
      });
    } catch (error) {
      throw new DashboardApiError(
        "network",
        "mcp_initialized",
        "تعذّر إكمال تهيئة جلسة MCP.",
        { cause: error },
      );
    }

    if (isUnauthorizedStatus(response.status)) {
      throw new DashboardApiError(
        "unauthorized",
        "mcp_initialized",
        "الواجهة غير مخوّلة لإكمال تهيئة جلسة MCP.",
        { status: response.status },
      );
    }

    if (!response.ok) {
      const payload = await parseJsonResponse(response, "mcp_initialized");
      if (isJsonRpcFailure(payload)) {
        throw new DashboardApiError(
          "protocol",
          "mcp_initialized",
          payload.error.message,
          { status: response.status, cause: payload.error.data },
        );
      }
      throw new DashboardApiError(
        "protocol",
        "mcp_initialized",
        "استجابة initialized غير متوقعة.",
        { status: response.status },
      );
    }
  }

  resetSession(): void {
    this.sessionPromise = null;
  }
}

export const dashboardMcpClient = new McpHttpClient();
