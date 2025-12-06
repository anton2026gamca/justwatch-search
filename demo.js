const TERMINAL_COMMANDS = {
  'help': {
    description: 'Show this help message',
    action: runHelp,
  },
  'clear': {
    description: 'Clear the terminal output',
    action: clearTerminal,
  },
  'python just_watch_search.py': {
    description: 'Run the JustWatch search script',
    action: runJustWatchSearch,
  },
}

let worker = null;
let pythonCode = '';
let workerReady = false;

let commandHistory = [];
let historyIndex = -1;

async function loadPythonScript() {
  try {
    const response = await fetch('just_watch_search.py');
    pythonCode = await response.text();
    return pythonCode;
  } catch (error) {
    appendOutput('Error loading Python script: ' + error.message, 'error');
    throw error;
  }
}

async function initPyodide() {
  try {
    updateStatus('loading', 'Initializing worker...');
    
    worker = new Worker('pyodide-worker.js');
    
    worker.onmessage = function(e) {
      const { type, state, message, text, success, error } = e.data;
      
      if (type === 'status') {
        updateStatus(state, message);
      } else if (type === 'initialized') {
        loadPythonScript().then(code => {
          worker.postMessage({ type: 'loadScript', code: code });
        });
      } else if (type === 'scriptLoaded') {
        workerReady = true;
        appendOutput('Python environment loaded successfully!', 'success');
        appendOutput('Type "help" to see available commands.', 'info');
        appendOutput('');
      } else if (type === 'output') {
        appendOutput(text);
      } else if (type === 'error') {
        appendOutput('Error: ' + (error || message), 'error');
      } else if (type === 'complete') {
        const input = document.getElementById('commandInput');
        input.disabled = false;
        if (success) {
          updateStatus('ready', 'Command completed successfully');
        } else {
          if (error && !error.includes('SystemExit')) {
            appendOutput('Error: ' + error, 'error');
          }
          updateStatus('ready', 'Command completed');
        }
        appendOutput('');
      }
    };
    
    worker.onerror = function(error) {
      updateStatus('error', 'Worker error: ' + error.message);
      appendOutput('Worker error: ' + error.message, 'error');
      console.error(error);
    };
    
    worker.postMessage({ type: 'init' });
  } catch (error) {
    updateStatus('error', 'Failed to initialize: ' + error.message);
    appendOutput('Initialization error: ' + error.message, 'error');
    console.error(error);
  }
}

function updateStatus(state, message) {
  const indicator = document.getElementById('statusIndicator');
  const text = document.getElementById('statusText');
  
  indicator.className = 'status-indicator ' + state;
  text.textContent = message;
}

function appendOutput(text, type = '') {
  const output = document.getElementById('terminalOutput');
  const line = document.createElement('div');
  line.className = 'output-line' + (type ? ' output-' + type : '');
  line.textContent = text;
  output.appendChild(line);
  output.scrollTop = output.scrollHeight;
}

function clearTerminal() {
  const output = document.getElementById('terminalOutput');
  output.innerHTML = '';
}

function runHelp() {
  appendOutput('Available commands:');
  for (const cmd in TERMINAL_COMMANDS) {
    appendOutput(`- ${cmd}: ${TERMINAL_COMMANDS[cmd].description}`);
  }
  appendOutput('');
}

async function runTerminalCommand(command) {
  let cmd = null;
  let args_raw = '';
  for (const key in TERMINAL_COMMANDS) {
    if (command.startsWith(key)) {
      cmd = TERMINAL_COMMANDS[key];
      args_raw = command.replace(key, '').trim();
      break;
    }
  }
  if (cmd) {
    commandHistory.push(command);
    historyIndex = commandHistory.length;
    function splitArgs(s) {
      const args = [];
      let cur = '';
      let inQuote = null;
      let esc = false;

      for (let i = 0; i < s.length; i++) {
        const ch = s[i];
        if (esc) {
          cur += ch;
          esc = false;
          continue;
        }
        if (ch === '\\') {
          esc = true;
          continue;
        }
        if (ch === '"' || ch === "'") {
          if (!inQuote) {
            inQuote = ch;
            continue;
          } else if (inQuote === ch) {
            inQuote = null;
            continue;
          } else {
            cur += ch;
            continue;
          }
        }
        if (ch === ' ' && !inQuote) {
          if (cur !== '') {
            args.push(cur);
            cur = '';
          }
          continue;
        }
        cur += ch;
      }
      if (esc) cur += '\\';
      if (cur !== '') args.push(cur);
      return args;
    }
    const args = splitArgs(args_raw);

    appendOutput('$ ' + command, 'info');
    const input = document.getElementById('commandInput');
    input.value = '';
    input.disabled = true;
    await cmd.action(args);
    input.disabled = false;
  } else {
    appendOutput('Unknown command: ' + command, 'error');
    appendOutput('Type "help" to see the list of available commands.', 'info');
  }
}

async function runJustWatchSearch(args) {
  if (!worker || !workerReady) {
    appendOutput('Python environment not ready yet. Please wait...', 'error');
    return;
  }

  updateStatus('loading', 'Running command...');
  
  worker.postMessage({ type: 'run', args: args });
}

document.getElementById('commandInput').addEventListener('keydown', async function(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    const cmd = this.value.trim();
    if (cmd) {
      await runTerminalCommand(cmd);
      this.value = '';
    }
  } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    e.preventDefault();
    if (commandHistory.length === 0) return;
    if (historyIndex < 0 || historyIndex > commandHistory.length) {
      historyIndex = commandHistory.length;
    }
    if (e.key === 'ArrowUp') {
      if (historyIndex > 0) {
        historyIndex--;
      }
    } else if (e.key === 'ArrowDown') {
      if (historyIndex < commandHistory.length - 1) {
        historyIndex++;
      } else {
        historyIndex = commandHistory.length;
        this.value = '';
        return;
      }
    }
    this.value = commandHistory[historyIndex] || '';
    this.setSelectionRange(this.value.length, this.value.length);
  } else if (e.key === 'Tab') {
    e.preventDefault();
    const currentInput = this.value.trim();
    const matchingCommands = Object.keys(TERMINAL_COMMANDS).filter(cmd => cmd.startsWith(currentInput));
    if (matchingCommands.length === 1) {
      this.value = matchingCommands[0];
      this.setSelectionRange(this.value.length, this.value.length);
    } else if (matchingCommands.length > 1) {
      appendOutput('Possible completions:');
      matchingCommands.forEach(cmd => appendOutput(`- ${cmd}`));
    }
  }
});

window.addEventListener('load', () => {
  initPyodide();
});