import React from "react";

const codeToRunOnClient = `(function() {
  try {
    var mode = localStorage.getItem('darkmode');
    var parsedMode = mode ? JSON.parse(mode) : 'dark';
    var htmlElement = document.getElementsByTagName("html")[0];
    htmlElement.className = parsedMode === 'dark' ? 'dark' : 'light';
  } catch (e) {
    document.getElementsByTagName("html")[0].className = 'dark';
  }
})();`;

export const onRenderBody = ({ setHeadComponents }) =>
  setHeadComponents([
    <script
      key="myscript"
      dangerouslySetInnerHTML={{ __html: codeToRunOnClient }}
    />,
  ]);
