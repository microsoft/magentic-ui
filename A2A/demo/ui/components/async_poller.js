import {
  LitElement,
  html,
} from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';

class AsyncPoller extends LitElement {
  static properties = {
    triggerEvent: {type: String},
    action: {type: Object},
    polling_interval: {type: Number},
  };

  render() {
    return html`<div></div>`;
  }

  firstUpdated() {
    if (this.polling_interval <= 0) {
      return;
    }
    if (this.action) {
      setTimeout(() => {
        this.runTimeout(this.action)
      }, this.polling_interval * 1000);
    }
  }

  runTimeout(action) {
    this.dispatchEvent(
      new MesopEvent(this.triggerEvent, {
        action: action,
      }),
    );
    if (this.polling_interval > 0) {
      setTimeout(() => {
        this.runTimeout();
      }, this.polling_interval * 1000);
    }
  }
}

customElements.define('async-action-component', AsyncPoller);
