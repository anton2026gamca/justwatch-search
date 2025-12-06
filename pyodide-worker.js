importScripts('https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js');

let pyodide = null;
let pythonCode = '';

async function initializePyodide() {
  self.postMessage({ type: 'status', state: 'loading', message: 'Loading Pyodide...' });
  pyodide = await loadPyodide();
  
  self.postMessage({ type: 'status', state: 'loading', message: 'Installing dependencies...' });
  await pyodide.loadPackage(['micropip']);
  const micropip = pyodide.pyimport('micropip');
  await micropip.install('requests');
  
  self.postMessage({ type: 'status', state: 'ready', message: 'Ready! Enter a command below.' });
  self.postMessage({ type: 'initialized' });
}

async function loadScript(code) {
  try {
    await pyodide.runPythonAsync(`
import importlib.util, sys
source = ${JSON.stringify(code)}
spec = importlib.util.spec_from_loader("just_watch_search", loader=None)
module = importlib.util.module_from_spec(spec)
module.__dict__['__name__'] = 'just_watch_search'
exec(source, module.__dict__)
sys.modules['just_watch_search'] = module
`);
    self.postMessage({ type: 'scriptLoaded' });
  } catch (error) {
    self.postMessage({ type: 'error', message: error.message });
  }
}

async function run(args) {
  try {
    pyodide.registerJsModule("output_handler", {
      send_output: (text) => {
        self.postMessage({ type: 'output', text: text });
      }
    });

    await pyodide.runPythonAsync(`
import sys
import builtins
import output_handler

_original_print = builtins.print

def custom_print(*args, sep=' ', end='\\n', file=None, flush=False):
  import io
  output = io.StringIO()
  _original_print(*args, sep=sep, end=end, file=output, flush=flush)
  text = output.getvalue()
  output_handler.send_output(text)

builtins.print = custom_print
sys.argv = ['just_watch_search.py'] + ${JSON.stringify(args)}
`);

    const exitCode = await pyodide.runPythonAsync(`
import just_watch_search
exit_code = 0
try:
  just_watch_search.main()
except EOFError:
  print("Interactive input is not supported in browser mode")
  exit_code = 1
except KeyboardInterrupt:
  print("Cancelled")
  exit_code = 130
except SystemExit as e:
  exit_code = e.code if hasattr(e, 'code') and e.code is not None else 0
except Exception as e:
  print(f"Error: {e}")
  exit_code = 1

builtins.print = _original_print

exit_code
`);

    pyodide.unregisterJsModule("output_handler");

    self.postMessage({ type: 'complete', success: true, exit_code: exitCode });
  } catch (error) {
    try {
      await pyodide.runPythonAsync('builtins.print = _original_print');
      pyodide.unregisterJsModule("output_handler");
    } catch (e) {}
    
    self.postMessage({ type: 'complete', success: false, error: error.message });
  }
}

self.onmessage = async function(e) {
  const { type, code, args } = e.data;
  
  if (type === 'init') {
    await initializePyodide();
  } else if (type === 'loadScript') {
    await loadScript(code);
  } else if (type === 'run') {
    await run(args);
  }
};
