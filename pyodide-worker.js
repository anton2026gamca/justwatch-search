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
import importlib.util, sys, ast
source = ${JSON.stringify(code)}
try:
  tree = ast.parse(source)
  defined = set()
  for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
      for t in node.targets:
        if isinstance(t, ast.Name):
          defined.add(t.id)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
      defined.add(node.name)
    if isinstance(node, ast.ImportFrom):
      for n in node.names:
        defined.add(n.asname or n.name)
    if isinstance(node, ast.Import):
      for n in node.names:
        defined.add(n.asname or n.name)
  if 'input' not in defined:
    class InputAwaiter(ast.NodeTransformer):
      def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'input':
          return ast.copy_location(ast.Await(value=node), node)
        return node
    new_tree = InputAwaiter().visit(tree)
    ast.fix_missing_locations(new_tree)
    source = ast.unparse(new_tree)
except Exception:
  pass

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
    const runId = Date.now() + Math.random();
    let currentStdinResolve = null;
    
    try {
      pyodide.unregisterJsModule("output_handler");
    } catch (e) {
      // Module might not exist, ignore
    }
    
    pyodide.registerJsModule("output_handler", {
      send_output: (text) => {
        self.postMessage({ type: 'output', text: text });
      },
      request_input_async: (prompt) => {
        self.postMessage({ type: 'stdin_request', prompt: prompt, runId: runId });
        return new Promise((resolve) => {
          currentStdinResolve = resolve;
        });
      }
    });

    const thisRunHandler = (response) => {
      if (currentStdinResolve) {
        const resolveFunc = currentStdinResolve;
        currentStdinResolve = null;
        resolveFunc(response);
      }
    };
    
    activeStdinHandler = thisRunHandler;

    await pyodide.runPythonAsync(`
import sys
import builtins

if 'output_handler' in sys.modules:
    del sys.modules['output_handler']

import output_handler

_original_print = builtins.print
_original_input = builtins.input
_original_stdout = sys.stdout
_original_stderr = sys.stderr

class StdoutRedirector:
  def write(self, s):
    output_handler.send_output(s)
  def flush(self):
    pass

class StderrRedirector(StdoutRedirector):
  pass

def custom_print(*args, sep=' ', end='\\n', file=None, flush=False):
  import io
  output = io.StringIO()
  _original_print(*args, sep=sep, end=end, file=output, flush=flush)
  text = output.getvalue()
  output_handler.send_output(text)

async def async_input(prompt=''):
  if prompt:
    custom_print(prompt, end='')
  import sys
  if 'output_handler' in sys.modules:
    del sys.modules['output_handler']
  import output_handler
  response = await output_handler.request_input_async(prompt)
  return response

builtins.print = custom_print
builtins.input = async_input
sys.stdout = StdoutRedirector()
sys.stderr = StderrRedirector()
sys.argv = ['just_watch_search.py'] + ${JSON.stringify(args)}
`);

    const exitCode = await pyodide.runPythonAsync(`
import just_watch_search
import asyncio

original_main = just_watch_search.main

exit_code = 0
try:
  await just_watch_search.main()
except EOFError:
  exit_code = 1
except KeyboardInterrupt:
  print("Cancelled")
  exit_code = 130
except SystemExit as e:
  exit_code = e.code if hasattr(e, 'code') and e.code is not None else 0
except Exception as e:
  import traceback
  print(f"Error: {e}")
  traceback.print_exc()
  exit_code = 1

builtins.print = _original_print
builtins.input = _original_input
sys.stdout = _original_stdout
sys.stderr = _original_stderr

exit_code
`);

    activeStdinHandler = null;
    pyodide.unregisterJsModule("output_handler");

    self.postMessage({ type: 'complete', success: true, exit_code: exitCode });
  } catch (error) {
    try {
      activeStdinHandler = null;
      await pyodide.runPythonAsync(`try:
  builtins.print = _original_print
  builtins.input = _original_input
  sys.stdout = _original_stdout
  sys.stderr = _original_stderr
except NameError:
  pass
`);
      pyodide.unregisterJsModule("output_handler");
    } catch (e) {}
    
    self.postMessage({ type: 'complete', success: false, error: error.message });
  }
}

let activeStdinHandler = null;
let runningCommand = false;
let commandQueue = [];

async function processCommandQueue() {
  if (runningCommand || commandQueue.length === 0) {
    return;
  }
  
  runningCommand = true;
  const args = commandQueue.shift();
  
  try {
    await run(args);
  } finally {
    runningCommand = false;
    if (commandQueue.length > 0) {
      processCommandQueue();
    }
  }
}

self.addEventListener('message', async function(e) {
  const { type, code, args } = e.data;
  
  if (type === 'init') {
    await initializePyodide();
  } else if (type === 'loadScript') {
    await loadScript(code);
  } else if (type === 'run') {
    commandQueue.push(args);
    processCommandQueue();
  } else if (type === 'stdin_response') {
    if (activeStdinHandler) {
      activeStdinHandler(e.data.response);
    }
  }
});
