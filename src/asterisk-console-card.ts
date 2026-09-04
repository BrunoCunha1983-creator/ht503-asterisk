import { LitElement, css, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { CALLSTATE, LegacyCardClient, sipCore } from "./sip-core";

declare global {
    interface Window {
        customCards?: Array<{ type: string; name: string; preview: boolean; description: string }>;
    }
}

interface EndpointConfig {
    name?: string;
    icon?: string;
    hidden?: boolean;
    registered_entity?: string;
    state_entity?: string;
    connected_entity?: string;
}

interface QuickNumber {
    number: string;
    name: string;
    icon?: string;
}

interface ConsoleAction {
    name: string;
    icon?: string;
    domain: string;
    service: string;
    service_data?: Record<string, unknown>;
    confirmation?: string;
}

interface AsteriskConsoleCardConfig {
    /** Compatibility fields from custom:sipjs-client-card. */
    server?: string;
    ringtone?: string;
    ringbacktone?: string;
    client?: string;
    clients?: Record<string, LegacyCardClient>;
    auto_answer?: boolean;
    title?: string;
    ami_entity?: string;
    auto_discover?: boolean;
    endpoints?: Record<string, EndpointConfig>;
    quick_numbers?: QuickNumber[];
    actions?: ConsoleAction[];
    show_keypad?: boolean;
    show_endpoints?: boolean;
    show_quick_numbers?: boolean;
    show_server_status?: boolean;
    dial_placeholder?: string;
}

interface ResolvedEndpoint extends EndpointConfig {
    extension: string;
    name: string;
}

const ACTIVE_STATES = new Set(["in use", "busy", "ringing", "ringing in use", "on hold"]);

@customElement("asterisk-console-card")
class AsteriskConsoleCard extends LitElement {
    @property({ attribute: false })
    public hass: any = sipCore.hass;

    @property({ attribute: false })
    public config: AsteriskConsoleCardConfig = {};

    @state()
    private dialNumber = "";

    private readonly sipUpdateHandler = () => this.requestUpdate();

    connectedCallback() {
        super.connectedCallback();
        window.addEventListener("sipcore-update", this.sipUpdateHandler);
    }

    disconnectedCallback() {
        window.removeEventListener("sipcore-update", this.sipUpdateHandler);
        super.disconnectedCallback();
    }

    setConfig(config: AsteriskConsoleCardConfig) {
        if (!config || typeof config !== "object") {
            throw new Error("A configuração do Asterisk Console Card é obrigatória.");
        }

        this.config = {
            title: "Asterisk / Issabel",
            auto_discover: true,
            show_keypad: true,
            show_endpoints: true,
            show_quick_numbers: true,
            show_server_status: true,
            dial_placeholder: "Extensão ou número",
            endpoints: {},
            quick_numbers: [],
            actions: [],
            ...config,
        };

        if (config.server || config.clients) {
            if (!config.server || !config.clients || Object.keys(config.clients).length === 0) {
                throw new Error("Para o modo compatível, define server: e pelo menos um cliente em clients:.");
            }
            void sipCore
                .configureFromLegacyCard({
                    server: config.server,
                    ringtone: config.ringtone,
                    ringbacktone: config.ringbacktone,
                    client: config.client,
                    clients: config.clients,
                    auto_answer: config.auto_answer,
                })
                .catch((error) => console.error("Asterisk Console Card: configuração SIP falhou", error));
        }
    }

    static getStubConfig() {
        return {
            title: "Asterisk / Issabel",
            auto_discover: true,
            show_keypad: true,
            endpoints: {
                "201": { name: "Telefone HT503" },
                "299": { name: "Linha analógica HT503" },
            },
        };
    }

    static get styles() {
        return css`
            :host {
                --asterisk-ok: var(--success-color, #43a047);
                --asterisk-warn: var(--warning-color, #f9a825);
                --asterisk-error: var(--error-color, #d32f2f);
                --asterisk-accent: var(--primary-color, #03a9f4);
            }

            ha-card {
                overflow: hidden;
            }

            .header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                padding: 18px 18px 10px;
            }

            .title {
                display: flex;
                align-items: center;
                gap: 10px;
                min-width: 0;
                font-size: 20px;
                font-weight: 600;
            }

            .title span {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .badges {
                display: flex;
                flex-wrap: wrap;
                justify-content: flex-end;
                gap: 6px;
            }

            .badge {
                display: inline-flex;
                align-items: center;
                gap: 5px;
                padding: 4px 8px;
                border-radius: 999px;
                color: var(--secondary-text-color);
                background: var(--secondary-background-color);
                font-size: 12px;
                white-space: nowrap;
            }

            .dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: var(--disabled-text-color);
            }

            .dot.ok {
                background: var(--asterisk-ok);
                box-shadow: 0 0 0 2px color-mix(in srgb, var(--asterisk-ok) 20%, transparent);
            }

            .dot.warn {
                background: var(--asterisk-warn);
            }

            .dot.error {
                background: var(--asterisk-error);
            }

            .call-panel {
                margin: 8px 16px 14px;
                padding: 16px;
                border-radius: 16px;
                color: var(--primary-text-color);
                background:
                    linear-gradient(135deg, color-mix(in srgb, var(--asterisk-accent) 18%, transparent), transparent 60%),
                    var(--secondary-background-color);
                border: 1px solid var(--divider-color);
            }

            .call-status {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 12px;
            }

            .call-identity {
                display: flex;
                align-items: center;
                gap: 12px;
                min-width: 0;
            }

            .call-identity ha-icon {
                width: 36px;
                height: 36px;
                color: var(--asterisk-accent);
            }

            .call-primary {
                font-weight: 600;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .call-secondary {
                margin-top: 2px;
                color: var(--secondary-text-color);
                font-size: 13px;
            }

            .duration {
                font-variant-numeric: tabular-nums;
                color: var(--secondary-text-color);
            }

            .dial-row {
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 8px;
                align-items: center;
            }

            ha-textfield {
                width: 100%;
            }

            .round-button {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 48px;
                height: 48px;
                border: 0;
                border-radius: 50%;
                cursor: pointer;
                color: #fff;
                background: var(--asterisk-ok);
            }

            .round-button[disabled] {
                cursor: default;
                opacity: 0.45;
            }

            .round-button.answer {
                background: var(--asterisk-ok);
            }

            .round-button.end {
                background: var(--asterisk-error);
            }

            .round-button.neutral {
                color: var(--primary-text-color);
                background: var(--card-background-color);
                border: 1px solid var(--divider-color);
            }

            .call-controls {
                display: flex;
                justify-content: center;
                gap: 14px;
            }

            .keypad {
                display: grid;
                grid-template-columns: repeat(3, minmax(58px, 1fr));
                gap: 8px;
                max-width: 330px;
                margin: 14px auto 0;
            }

            .key {
                min-height: 46px;
                border: 1px solid var(--divider-color);
                border-radius: 12px;
                cursor: pointer;
                color: var(--primary-text-color);
                background: var(--card-background-color);
                font-size: 18px;
                font-weight: 600;
            }

            .key:active,
            .endpoint:active,
            .shortcut:active,
            .action:active {
                transform: scale(0.98);
            }

            .section {
                padding: 0 16px 14px;
            }

            .section-title {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin: 4px 2px 8px;
                color: var(--secondary-text-color);
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 0.04em;
                text-transform: uppercase;
            }

            .endpoint-list {
                display: grid;
                gap: 6px;
            }

            .endpoint {
                display: grid;
                grid-template-columns: auto minmax(0, 1fr) auto;
                align-items: center;
                gap: 10px;
                width: 100%;
                padding: 10px 12px;
                border: 0;
                border-radius: 12px;
                cursor: pointer;
                text-align: left;
                color: var(--primary-text-color);
                background: var(--secondary-background-color);
            }

            .endpoint ha-icon {
                color: var(--secondary-text-color);
            }

            .endpoint-name {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                font-weight: 500;
            }

            .endpoint-meta {
                display: block;
                margin-top: 2px;
                color: var(--secondary-text-color);
                font-size: 12px;
                font-weight: 400;
            }

            .endpoint-state {
                display: flex;
                align-items: center;
                gap: 7px;
                color: var(--secondary-text-color);
                font-size: 12px;
                white-space: nowrap;
            }

            .shortcut-grid,
            .action-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 8px;
            }

            .shortcut,
            .action {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                min-height: 42px;
                padding: 6px 10px;
                border: 1px solid var(--divider-color);
                border-radius: 12px;
                cursor: pointer;
                color: var(--primary-text-color);
                background: var(--card-background-color);
            }

            .empty {
                padding: 12px;
                border: 1px dashed var(--divider-color);
                border-radius: 12px;
                color: var(--secondary-text-color);
                text-align: center;
                font-size: 13px;
            }

            .warning {
                display: flex;
                gap: 8px;
                align-items: flex-start;
                margin: 0 16px 14px;
                padding: 10px 12px;
                border-radius: 12px;
                color: var(--warning-color, #f9a825);
                background: color-mix(in srgb, var(--warning-color, #f9a825) 12%, transparent);
                font-size: 13px;
            }

            @media (max-width: 430px) {
                .header {
                    align-items: flex-start;
                    flex-direction: column;
                }

                .badges {
                    justify-content: flex-start;
                }

                .endpoint-state .label {
                    display: none;
                }
            }
        `;
    }

    private get sipRegistered(): boolean {
        try {
            return Boolean(sipCore.ua && sipCore.registered);
        } catch (_error) {
            return false;
        }
    }

    private get amiEntityId(): string | undefined {
        if (this.config.ami_entity) return this.config.ami_entity;
        return this.findEntityByFriendlyName("AMI Connected", "binary_sensor");
    }

    private get amiConnected(): boolean | null {
        const entityId = this.amiEntityId;
        if (!entityId || !this.hass?.states?.[entityId]) return null;
        return this.hass.states[entityId].state === "on";
    }

    private findEntityByFriendlyName(friendlyName: string, domain?: string): string | undefined {
        const states = this.hass?.states || {};
        return Object.keys(states).find((entityId) => {
            if (domain && !entityId.startsWith(`${domain}.`)) return false;
            return states[entityId]?.attributes?.friendly_name === friendlyName;
        });
    }

    private resolveEndpoints(): ResolvedEndpoint[] {
        const found = new Map<string, ResolvedEndpoint>();
        const states = this.hass?.states || {};

        if (this.config.auto_discover !== false) {
            Object.entries(states).forEach(([entityId, rawState]: [string, any]) => {
                if (!entityId.startsWith("binary_sensor.")) return;
                const friendlyName = rawState?.attributes?.friendly_name || "";
                const match = friendlyName.match(/^(.+) Registered$/i);
                if (!match) return;

                const extension = match[1];
                found.set(extension, {
                    extension,
                    name: extension,
                    registered_entity: entityId,
                    state_entity: this.findEntityByFriendlyName(`${extension} State`, "sensor"),
                    connected_entity: this.findEntityByFriendlyName(`${extension} Connected Line`, "sensor"),
                });
            });
        }

        Object.entries(this.config.endpoints || {}).forEach(([extension, endpoint]) => {
            const discovered = found.get(extension) || { extension, name: extension };
            found.set(extension, {
                ...discovered,
                ...endpoint,
                extension,
                name: endpoint.name || discovered.name || extension,
            });
        });

        return [...found.values()]
            .filter((endpoint) => !endpoint.hidden)
            .sort((a, b) => a.extension.localeCompare(b.extension, undefined, { numeric: true }));
    }

    private endpointState(endpoint: ResolvedEndpoint): string {
        const state = endpoint.state_entity ? this.hass?.states?.[endpoint.state_entity]?.state : undefined;
        if (state && state !== "unknown" && state !== "unavailable") return state;
        const registered = endpoint.registered_entity
            ? this.hass?.states?.[endpoint.registered_entity]?.state
            : undefined;
        if (registered === "on") return "Not in use";
        if (registered === "off") return "Unavailable";
        return "Unknown";
    }

    private endpointConnectedLine(endpoint: ResolvedEndpoint): string | undefined {
        if (!endpoint.connected_entity) return undefined;
        const state = this.hass?.states?.[endpoint.connected_entity]?.state;
        if (!state || ["none", "unknown", "unavailable"].includes(state.toLowerCase())) return undefined;
        return state;
    }

    private stateLabel(state: string): string {
        const labels: Record<string, string> = {
            "not in use": "Livre",
            "in use": "Em chamada",
            busy: "Ocupado",
            unavailable: "Indisponível",
            ringing: "A tocar",
            "ringing in use": "Chamada em espera",
            "on hold": "Em espera",
            unknown: "Desconhecido",
        };
        return labels[state.toLowerCase()] || state;
    }

    private stateClass(state: string): string {
        const normalized = state.toLowerCase();
        if (["unavailable", "unknown"].includes(normalized)) return "error";
        if (ACTIVE_STATES.has(normalized)) return "warn";
        return "ok";
    }

    private callLabel(): { primary: string; secondary: string; icon: string } {
        const endpoints = this.resolveEndpoints();
        const remote = sipCore.remoteExtension || "";
        const remoteName = endpoints.find((item) => item.extension === remote)?.name || sipCore.remoteName || remote;

        switch (sipCore.callState) {
            case CALLSTATE.INCOMING:
                return { primary: `Chamada de ${remoteName}`, secondary: remote, icon: "mdi:phone-incoming" };
            case CALLSTATE.OUTGOING:
                return { primary: `A ligar para ${remoteName}`, secondary: remote, icon: "mdi:phone-outgoing" };
            case CALLSTATE.CONNECTING:
                return { primary: `A estabelecer chamada com ${remoteName}`, secondary: remote, icon: "mdi:phone-sync" };
            case CALLSTATE.CONNECTED:
                return { primary: remoteName, secondary: `Ligado a ${remote}`, icon: "mdi:phone-in-talk" };
            default:
                return {
                    primary: "Sem chamada ativa",
                    secondary: this.sipRegistered
                        ? `Extensão ${sipCore.user?.extension || "—"} pronta`
                        : "Cliente SIP não registado",
                    icon: "mdi:phone-classic",
                };
        }
    }

    private sanitizeNumber(value: string): string {
        return value.replace(/[^0-9A-Da-d*#+]/g, "").slice(0, 64);
    }

    private async startCall(number?: string) {
        const destination = this.sanitizeNumber(number ?? this.dialNumber);
        if (!destination || !this.sipRegistered || sipCore.callState !== CALLSTATE.IDLE) return;
        this.dialNumber = destination;
        await sipCore.startCall(destination);
    }

    private pressKey(key: string) {
        if (sipCore.callState === CALLSTATE.CONNECTED && sipCore.RTCSession) {
            sipCore.RTCSession.sendDTMF(key);
        } else {
            this.dialNumber = this.sanitizeNumber(`${this.dialNumber}${key}`);
        }
    }

    private toggleMute() {
        if (!sipCore.RTCSession) return;
        if (sipCore.RTCSession.isMuted().audio) sipCore.RTCSession.unmute({ audio: true });
        else sipCore.RTCSession.mute({ audio: true });
        this.requestUpdate();
    }

    private async runAction(action: ConsoleAction) {
        if (action.confirmation && !window.confirm(action.confirmation)) return;
        await this.hass.callService(action.domain, action.service, action.service_data || {});
    }

    private renderEndpoint(endpoint: ResolvedEndpoint) {
        const state = this.endpointState(endpoint);
        const connectedLine = this.endpointConnectedLine(endpoint);
        const disabled = !this.sipRegistered || sipCore.callState !== CALLSTATE.IDLE;
        return html`
            <button class="endpoint" ?disabled=${disabled} @click=${() => this.startCall(endpoint.extension)}>
                <ha-icon .icon=${endpoint.icon || "mdi:phone"}></ha-icon>
                <span class="endpoint-name">
                    ${endpoint.name}
                    <span class="endpoint-meta">${endpoint.extension}${connectedLine ? ` · com ${connectedLine}` : ""}</span>
                </span>
                <span class="endpoint-state">
                    <span class="dot ${this.stateClass(state)}"></span>
                    <span class="label">${this.stateLabel(state)}</span>
                </span>
            </button>
        `;
    }

    render() {
        const call = this.callLabel();
        const callState = sipCore.callState;
        const inCall = callState !== CALLSTATE.IDLE;
        const muted = Boolean(sipCore.RTCSession?.isMuted().audio);
        const endpoints = this.resolveEndpoints();
        const ami = this.amiConnected;
        const activeCount = endpoints.filter((endpoint) => ACTIVE_STATES.has(this.endpointState(endpoint).toLowerCase())).length;
        const keypad = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"];

        return html`
            <ha-card>
                <div class="header">
                    <div class="title">
                        <ha-icon icon="mdi:asterisk"></ha-icon>
                        <span>${this.config.title}</span>
                    </div>
                    <div class="badges">
                        <span class="badge">
                            <span class="dot ${this.sipRegistered ? "ok" : "error"}"></span>
                            SIP ${this.sipRegistered ? "registado" : "offline"}
                        </span>
                        ${this.config.show_server_status !== false
                            ? html`
                                  <span class="badge">
                                      <span class="dot ${ami === null ? "warn" : ami ? "ok" : "error"}"></span>
                                      AMI ${ami === null ? "não configurado" : ami ? "ligado" : "offline"}
                                  </span>
                              `
                            : nothing}
                        ${activeCount > 0 ? html`<span class="badge">${activeCount} ativa${activeCount === 1 ? "" : "s"}</span>` : nothing}
                    </div>
                </div>

                ${!this.sipRegistered
                    ? html`
                          <div class="warning">
                              <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
                              <span>O cliente WebRTC ainda não está registado no Asterisk. Confirma o WSS, certificado e credenciais da extensão.</span>
                          </div>
                      `
                    : nothing}

                <div class="call-panel">
                    <div class="call-status">
                        <div class="call-identity">
                            <ha-icon .icon=${call.icon}></ha-icon>
                            <div>
                                <div class="call-primary">${call.primary}</div>
                                <div class="call-secondary">${call.secondary}</div>
                            </div>
                        </div>
                        <div class="duration">${sipCore.callDuration}</div>
                    </div>

                    ${!inCall
                        ? html`
                              <div class="dial-row">
                                  <ha-textfield
                                      .value=${this.dialNumber}
                                      .label=${this.config.dial_placeholder}
                                      inputmode="tel"
                                      @input=${(event: InputEvent) => {
                                          this.dialNumber = this.sanitizeNumber((event.target as HTMLInputElement).value);
                                      }}
                                      @keydown=${(event: KeyboardEvent) => {
                                          if (event.key === "Enter") this.startCall();
                                      }}
                                  ></ha-textfield>
                                  <button
                                      class="round-button"
                                      title="Ligar"
                                      ?disabled=${!this.sipRegistered || !this.dialNumber}
                                      @click=${() => this.startCall()}
                                  >
                                      <ha-icon icon="mdi:phone"></ha-icon>
                                  </button>
                              </div>
                          `
                        : html`
                              <div class="call-controls">
                                  ${callState === CALLSTATE.INCOMING
                                      ? html`
                                            <button class="round-button answer" title="Atender" @click=${() => sipCore.answerCall()}>
                                                <ha-icon icon="mdi:phone"></ha-icon>
                                            </button>
                                        `
                                      : nothing}
                                  <button class="round-button neutral" title=${muted ? "Ativar microfone" : "Silenciar microfone"} @click=${() => this.toggleMute()}>
                                      <ha-icon .icon=${muted ? "mdi:microphone-off" : "mdi:microphone"}></ha-icon>
                                  </button>
                                  <button class="round-button end" title="Desligar" @click=${() => sipCore.endCall()}>
                                      <ha-icon icon="mdi:phone-hangup"></ha-icon>
                                  </button>
                              </div>
                          `}

                    ${this.config.show_keypad !== false
                        ? html`
                              <div class="keypad">
                                  ${keypad.map((key) => html`<button class="key" @click=${() => this.pressKey(key)}>${key}</button>`)}
                              </div>
                          `
                        : nothing}
                </div>

                ${this.config.show_quick_numbers !== false && (this.config.quick_numbers || []).length
                    ? html`
                          <div class="section">
                              <div class="section-title">Atalhos</div>
                              <div class="shortcut-grid">
                                  ${(this.config.quick_numbers || []).map(
                                      (item) => html`
                                          <button
                                              class="shortcut"
                                              ?disabled=${!this.sipRegistered || inCall}
                                              @click=${() => this.startCall(item.number)}
                                          >
                                              <ha-icon .icon=${item.icon || "mdi:phone-forward"}></ha-icon>
                                              <span>${item.name}</span>
                                          </button>
                                      `,
                                  )}
                              </div>
                          </div>
                      `
                    : nothing}

                ${this.config.show_endpoints !== false
                    ? html`
                          <div class="section">
                              <div class="section-title">
                                  <span>Extensões</span>
                                  <span>${endpoints.length}</span>
                              </div>
                              <div class="endpoint-list">
                                  ${endpoints.length
                                      ? endpoints.map((endpoint) => this.renderEndpoint(endpoint))
                                      : html`
                                            <div class="empty">
                                                Instala/configura a integração Asterisk ou define <code>endpoints:</code> no cartão.
                                            </div>
                                        `}
                              </div>
                          </div>
                      `
                    : nothing}

                ${(this.config.actions || []).length
                    ? html`
                          <div class="section">
                              <div class="section-title">Ações</div>
                              <div class="action-grid">
                                  ${(this.config.actions || []).map(
                                      (action) => html`
                                          <button class="action" @click=${() => this.runAction(action)}>
                                              <ha-icon .icon=${action.icon || "mdi:play-circle-outline"}></ha-icon>
                                              <span>${action.name}</span>
                                          </button>
                                      `,
                                  )}
                              </div>
                          </div>
                      `
                    : nothing}
            </ha-card>
        `;
    }

    getCardSize() {
        return 8;
    }
}

window.customCards = window.customCards || [];
window.customCards.push({
    type: "asterisk-console-card",
    name: "Asterisk / Issabel Console Card BC",
    preview: true,
    description: "Softphone e painel de estado Asterisk para Home Assistant",
});
