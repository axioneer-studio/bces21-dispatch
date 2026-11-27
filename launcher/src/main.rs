use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};
#[cfg(target_os = "linux")]
use std::env;
#[cfg(all(unix, not(target_os = "linux")))]
use std::process::Stdio;
#[cfg(unix)]
use std::time::Duration;
use std::{
    collections::hash_map::DefaultHasher,
    fs,
    hash::{Hash, Hasher},
    path::{Path, PathBuf},
    process::Command,
};
#[cfg(unix)]
use tokio::time::sleep;
use tokio::{
    io::{AsyncBufReadExt, BufReader as AsyncBufReader},
    process::{Child, Command as TokioCommand},
};

#[derive(Parser)]
#[command(
    name = "bces-dev",
    version,
    about = "BCES Dispatch development launcher"
)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,

    /// Project root (defaults to the directory containing this executable's current working directory)
    #[arg(long, global = true)]
    root: Option<PathBuf>,
}

#[derive(Subcommand)]
enum Commands {
    /// Prepare dependencies and start backend + frontend
    Start,
    /// Stop the processes started by this launcher
    Stop,
    /// Display launcher process status
    Status,
}

#[derive(Clone)]
struct Paths {
    backend: PathBuf,
    frontend: PathBuf,
    python: PathBuf,
    state: PathBuf,
    frontend_marker: PathBuf,
    backend_pid_file: PathBuf,
    frontend_pid_file: PathBuf,
}

#[derive(Serialize, Deserialize, Default)]
#[serde(default)]
struct State {
    backend_pid: Option<u32>,
    frontend_pid: Option<u32>,
    backend_group: Option<bool>,
    frontend_group: Option<bool>,
    backend_shell_pid: Option<u32>,
    frontend_shell_pid: Option<u32>,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let root = match cli.root {
        Some(path) => path.canonicalize().context("Cannot resolve --root")?,
        None => discover_project_root(std::env::current_dir()?)?,
    };
    let paths = build_paths(root)?;

    match cli.command.unwrap_or(Commands::Start) {
        Commands::Start => start(paths).await,
        Commands::Stop => stop(&paths),
        Commands::Status => status(&paths),
    }
}

fn discover_project_root(start: PathBuf) -> Result<PathBuf> {
    let start = start
        .canonicalize()
        .context("Cannot resolve current directory")?;

    // Allow running from either the repository root or its launcher/ subdirectory.
    for candidate in
        std::iter::once(start.clone()).chain(start.ancestors().skip(1).map(Path::to_path_buf))
    {
        if candidate.join("backend").join("requirements.txt").is_file()
            && candidate.join("frontend").join("package.json").is_file()
        {
            return Ok(candidate);
        }
    }

    bail!(
        "Could not locate the BCES project root from {}. Run the launcher from the repository or pass --root <project-path>.",
        start.display()
    )
}

fn build_paths(root: PathBuf) -> Result<Paths> {
    let backend = root.join("backend");
    let frontend = root.join("frontend");

    if !backend.join("requirements.txt").is_file() {
        bail!(
            "backend/requirements.txt not found under {}",
            root.display()
        );
    }
    if !frontend.join("package.json").is_file() {
        bail!("frontend/package.json not found under {}", root.display());
    }

    let mut hasher = DefaultHasher::new();
    root.to_string_lossy().to_lowercase().hash(&mut hasher);
    let project_id = format!("{:x}", hasher.finish());

    let cache_root = dirs::cache_dir()
        .or_else(dirs::home_dir)
        .context("Cannot determine user cache directory")?
        .join("bces-dev")
        .join(project_id);
    fs::create_dir_all(&cache_root)?;

    let python = if cfg!(windows) {
        backend.join(".venv").join("Scripts").join("python.exe")
    } else {
        cache_root.join("venv").join("bin").join("python")
    };

    Ok(Paths {
        backend,
        frontend,
        python,
        state: cache_root.join("processes.json"),
        frontend_marker: cache_root.join("frontend-dependencies.hash"),
        backend_pid_file: cache_root.join("backend-terminal.pid"),
        frontend_pid_file: cache_root.join("frontend-terminal.pid"),
    })
}

async fn start(paths: Paths) -> Result<()> {
    ensure_not_running(&paths)?;

    prepare_backend(&paths)?;
    prepare_frontend(&paths)?;

    println!("[BCES] Starting BCES Dispatch development environment");
    println!("[BCES] Backend : http://localhost:8000");
    println!("[BCES] Frontend: http://localhost:3000");
    println!("[BCES] Docs    : http://localhost:8000/docs");
    if cfg!(windows) || cfg!(target_os = "linux") {
        println!("[BCES] Backend and frontend are running in separate terminal windows.");
        println!("[BCES] Close them through this launcher with Ctrl+C or `bces-dev stop`.\n");
    } else {
        println!("[BCES] Logs are prefixed with [BACKEND] and [FRONTEND].");
        println!("[BCES] Press Ctrl+C to stop both services.\n");
    }

    check_port(8000)?;
    check_port(3000)?;

    let _ = fs::remove_file(&paths.backend_pid_file);
    let _ = fs::remove_file(&paths.frontend_pid_file);

    let mut backend = spawn_backend(&paths)?;
    let mut frontend = match spawn_frontend(&paths) {
        Ok(child) => child,
        Err(error) => {
            terminate_child(&mut backend, None).await;
            return Err(error);
        }
    };

    #[cfg(target_os = "linux")]
    let (backend_shell_pid, frontend_shell_pid) = tokio::join!(
        read_pid_file(&paths.backend_pid_file),
        read_pid_file(&paths.frontend_pid_file),
    );
    #[cfg(not(target_os = "linux"))]
    let (backend_shell_pid, frontend_shell_pid) = (None, None);

    let state = State {
        backend_pid: backend.id(),
        frontend_pid: frontend.id(),
        backend_group: Some(cfg!(all(unix, not(target_os = "linux")))),
        frontend_group: Some(cfg!(all(unix, not(target_os = "linux")))),
        backend_shell_pid,
        frontend_shell_pid,
    };
    save_state(&paths.state, &state)?;

    let backend_logs = pipe_logs(backend.stdout.take(), backend.stderr.take(), "BACKEND");
    let frontend_logs = pipe_logs(frontend.stdout.take(), frontend.stderr.take(), "FRONTEND");

    tokio::pin!(backend_logs);
    tokio::pin!(frontend_logs);

    let outcome = tokio::select! {
        result = backend.wait() => {
            println!("\n[BCES] Backend terminal exited: {result:?}");
            "backend"
        }
        result = frontend.wait() => {
            println!("\n[BCES] Frontend terminal exited: {result:?}");
            "frontend"
        }
        signal = tokio::signal::ctrl_c() => {
            signal.context("Failed to listen for Ctrl+C")?;
            println!("\n[BCES] Ctrl+C received.");
            "signal"
        }
    };

    terminate_child(&mut backend, backend_shell_pid).await;
    terminate_child(&mut frontend, frontend_shell_pid).await;
    let _ = tokio::join!(backend_logs, frontend_logs);
    let _ = fs::remove_file(&paths.state);
    let _ = fs::remove_file(&paths.backend_pid_file);
    let _ = fs::remove_file(&paths.frontend_pid_file);

    println!("[BCES] Both services stopped ({outcome}).");
    Ok(())
}

fn prepare_backend(paths: &Paths) -> Result<()> {
    let venv_dir = paths
        .python
        .parent()
        .and_then(Path::parent)
        .context("Could not determine Python virtual environment directory")?;

    if !paths.python.is_file() {
        println!("[BCES] Creating Python virtual environment...");
        if cfg!(windows) {
            let status = Command::new("py")
                .args(["-3", "-m", "venv"])
                .arg(venv_dir)
                .status()
                .or_else(|_| {
                    Command::new("python")
                        .args(["-m", "venv"])
                        .arg(venv_dir)
                        .status()
                })?;
            if !status.success() {
                bail!("Could not create Windows virtualenv. Install Python 3.11+ and the venv component.");
            }
        } else {
            let status = Command::new("python3")
                .args(["-m", "venv"])
                .arg(venv_dir)
                .status()
                .context("python3 not found. Install Python 3.11+ and python3-venv.")?;
            if !status.success() {
                bail!("Could not create Python virtualenv. Install python3-venv.");
            }
        }
    }

    if !paths.python.is_file() {
        bail!(
            "Python virtualenv executable not found: {}",
            paths.python.display()
        );
    }

    // A previous run may have written a requirements hash even though pip installation
    // was interrupted. Verify pip itself and run pip install on every start; pip is
    // incremental and will only install/update what is actually missing.
    let pip_check = Command::new(&paths.python)
        .args(["-m", "pip", "--version"])
        .current_dir(&paths.backend)
        .status()
        .context("Could not check pip in the backend virtualenv")?;

    if !pip_check.success() {
        println!("[BCES] pip is missing; bootstrapping it with ensurepip...");
        run_python_module(&paths.python, &["ensurepip", "--upgrade"], &paths.backend)?;
    }

    println!("[BCES] Installing/checking Python requirements...");
    run_python_module(
        &paths.python,
        &[
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            "requirements.txt",
        ],
        &paths.backend,
    )?;

    // Uvicorn is the ASGI server used by this launcher. Keep the launcher resilient
    // if it is accidentally absent from requirements.txt or a previous install was partial.
    let uvicorn_check = Command::new(&paths.python)
        .args(["-c", "import uvicorn"])
        .current_dir(&paths.backend)
        .status()
        .context("Could not verify the Uvicorn installation")?;
    if !uvicorn_check.success() {
        println!("[BCES] Uvicorn is missing; installing uvicorn[standard]...");
        run_python_module(
            &paths.python,
            &[
                "pip",
                "install",
                "--disable-pip-version-check",
                "uvicorn[standard]",
            ],
            &paths.backend,
        )?;
    }

    let pip_check = Command::new(&paths.python)
        .args(["-m", "pip", "check"])
        .current_dir(&paths.backend)
        .status()
        .context("Could not validate Python dependencies")?;
    if !pip_check.success() {
        bail!("Python dependency validation failed. Review the pip errors above.");
    }

    let env = paths.backend.join(".env");
    let example = paths.backend.join(".env.example");
    if !env.exists() && example.exists() {
        fs::copy(example, env)?;
        println!("[BCES] Created backend/.env from .env.example. Check your credentials.");
    } else if !env.exists() {
        bail!("backend/.env and backend/.env.example are both missing.");
    }

    Ok(())
}

fn run_python_module(python: &Path, args: &[&str], cwd: &Path) -> Result<()> {
    let status = Command::new(python)
        .arg("-m")
        .args(args)
        .current_dir(cwd)
        .status()
        .with_context(|| {
            format!(
                "Could not execute {} -m {}",
                python.display(),
                args.join(" ")
            )
        })?;

    if !status.success() {
        bail!("Python command failed: -m {}", args.join(" "));
    }
    Ok(())
}

fn prepare_frontend(paths: &Paths) -> Result<()> {
    ensure_command("node", &["--version"], &paths.frontend)
        .context("Node.js is not available in this environment. Install Node.js in the same OS where you run bces-dev.")?;
    ensure_command("npm", &["--version"], &paths.frontend)
        .context("npm is not available in this environment. Install Node.js/npm in the same OS where you run bces-dev.")?;

    let package_json = paths.frontend.join("package.json");
    let lock_file = paths.frontend.join("package-lock.json");
    let mut hasher = DefaultHasher::new();
    fs::read(&package_json)?.hash(&mut hasher);
    if lock_file.is_file() {
        fs::read(&lock_file)?.hash(&mut hasher);
    }
    let current_hash = format!("{:x}", hasher.finish());
    let previous_hash = fs::read_to_string(&paths.frontend_marker).unwrap_or_default();
    let node_modules_exists = paths.frontend.join("node_modules").is_dir();
    let installed_tree_valid = node_modules_exists && npm_dependencies_valid(&paths.frontend);

    if !installed_tree_valid || previous_hash != current_hash {
        println!("[BCES] Installing/checking frontend npm dependencies...");
        if lock_file.is_file() {
            run_npm(&paths.frontend, &["ci"])?;
        } else {
            run_npm(&paths.frontend, &["install"])?;
        }
        fs::write(&paths.frontend_marker, current_hash)?;
    } else {
        println!("[BCES] Frontend npm dependencies are up to date; skipping installation.");
    }

    Ok(())
}

fn npm_dependencies_valid(cwd: &Path) -> bool {
    let command_cwd = command_cwd(cwd);
    let output = if cfg!(windows) {
        Command::new("cmd")
            .args(["/C", "npm.cmd", "ls", "--all"])
            .current_dir(command_cwd)
            .output()
    } else {
        Command::new("npm")
            .args(["ls", "--all"])
            .current_dir(command_cwd)
            .output()
    };

    output
        .map(|result| result.status.success())
        .unwrap_or(false)
}

fn run_npm(cwd: &Path, args: &[&str]) -> Result<()> {
    let command_cwd = command_cwd(cwd);
    let status = if cfg!(windows) {
        Command::new("cmd")
            .args(["/C", "npm.cmd"])
            .args(args)
            .current_dir(command_cwd)
            .status()?
    } else {
        Command::new("npm")
            .args(args)
            .current_dir(command_cwd)
            .status()?
    };
    if !status.success() {
        bail!("npm {} failed", args.join(" "));
    }
    Ok(())
}

fn ensure_command(program: &str, args: &[&str], cwd: &Path) -> Result<()> {
    let command_cwd = command_cwd(cwd);
    let status = if cfg!(windows) && program == "npm" {
        Command::new("cmd")
            .args(["/C", "npm.cmd"])
            .args(args)
            .current_dir(command_cwd)
            .status()?
    } else {
        Command::new(program)
            .args(args)
            .current_dir(command_cwd)
            .status()?
    };
    if !status.success() {
        bail!("{program} check failed");
    }
    Ok(())
}

#[cfg(windows)]
fn command_cwd(path: &Path) -> PathBuf {
    let raw = path.to_string_lossy();
    if let Some(rest) = raw.strip_prefix(r"\\?\UNC\") {
        PathBuf::from(format!(r"\\{}", rest))
    } else if let Some(rest) = raw.strip_prefix(r"\\?\") {
        PathBuf::from(rest)
    } else {
        path.to_path_buf()
    }
}

#[cfg(not(windows))]
fn command_cwd(path: &Path) -> PathBuf {
    path.to_path_buf()
}

fn spawn_backend(paths: &Paths) -> Result<Child> {
    #[cfg(windows)]
    {
        let script = format!(
            "$Host.UI.RawUI.WindowTitle = 'BCES Dispatch - Backend'; Set-Location -LiteralPath {}; Write-Host '[BCES] Starting FastAPI...' -ForegroundColor Cyan; & {} -m uvicorn main:app --reload --host 0.0.0.0 --port 8000; $exitCode = $LASTEXITCODE; if ($null -eq $exitCode) {{ $exitCode = 0 }}; Write-Host ''; if ($exitCode -eq 0) {{ Write-Host '[BCES] FastAPI stopped normally.' -ForegroundColor Yellow }} else {{ Write-Host ('[BCES] FastAPI stopped with exit code ' + $exitCode) -ForegroundColor Red }}; Write-Host '[BCES] This PowerShell window remains open for debugging.' -ForegroundColor Yellow",
            ps_quote(&paths.backend),
            ps_quote(&paths.python),
        );
        return spawn_windows_console(&script).context("Could not open the FastAPI console");
    }

    #[cfg(target_os = "linux")]
    {
        let args = vec![
            "-m".to_string(),
            "uvicorn".to_string(),
            "main:app".to_string(),
            "--reload".to_string(),
            "--host".to_string(),
            "0.0.0.0".to_string(),
            "--port".to_string(),
            "8000".to_string(),
        ];
        return spawn_linux_terminal(
            "BCES Dispatch - Backend",
            &paths.backend,
            &paths.backend_pid_file,
            &paths.python,
            &args,
        )
        .context("Could not open a Linux terminal for FastAPI");
    }

    #[cfg(all(unix, not(target_os = "linux")))]
    {
        let mut command = TokioCommand::new(&paths.python);
        command
            .args([
                "-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000",
            ])
            .current_dir(&paths.backend)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        configure_process_group(&mut command);
        command.spawn().context("Could not start FastAPI/Uvicorn")
    }
}

fn spawn_frontend(paths: &Paths) -> Result<Child> {
    #[cfg(windows)]
    {
        let script = format!(
            "$Host.UI.RawUI.WindowTitle = 'BCES Dispatch - Frontend'; Set-Location -LiteralPath {}; Write-Host '[BCES] Starting Nuxt...' -ForegroundColor Cyan; & npm.cmd run dev -- --port 3000; $exitCode = $LASTEXITCODE; if ($null -eq $exitCode) {{ $exitCode = 0 }}; Write-Host ''; if ($exitCode -eq 0) {{ Write-Host '[BCES] Nuxt stopped normally.' -ForegroundColor Yellow }} else {{ Write-Host ('[BCES] Nuxt stopped with exit code ' + $exitCode) -ForegroundColor Red }}; Write-Host '[BCES] This PowerShell window remains open for debugging.' -ForegroundColor Yellow",
            ps_quote(&paths.frontend),
        );
        return spawn_windows_console(&script).context("Could not open the Nuxt console");
    }

    #[cfg(target_os = "linux")]
    {
        let args = vec![
            "run".to_string(),
            "dev".to_string(),
            "--".to_string(),
            "--port".to_string(),
            "3000".to_string(),
        ];
        return spawn_linux_terminal(
            "BCES Dispatch - Frontend",
            &paths.frontend,
            &paths.frontend_pid_file,
            Path::new("npm"),
            &args,
        )
        .context("Could not open a Linux terminal for Nuxt");
    }

    #[cfg(all(unix, not(target_os = "linux")))]
    {
        let mut command = TokioCommand::new("npm");
        command
            .args(["run", "dev", "--", "--port", "3000"])
            .current_dir(&paths.frontend)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        configure_process_group(&mut command);
        command.spawn().context("Could not start Nuxt")
    }
}

#[cfg(target_os = "linux")]
fn spawn_linux_terminal(
    title: &str,
    cwd: &Path,
    pid_file: &Path,
    program: &Path,
    args: &[String],
) -> Result<Child> {
    let terminal = find_linux_terminal()
        .context("No supported terminal emulator found. Install GNOME Terminal, Konsole, XFCE Terminal, XTerm or another supported terminal.")?;
    let executable_name = terminal
        .file_name()
        .and_then(std::ffi::OsStr::to_str)
        .unwrap_or("");

    let command = std::iter::once(program.to_string_lossy().into_owned())
        .chain(args.iter().cloned())
        .map(|part| shell_quote(&part))
        .collect::<Vec<_>>()
        .join(" ");

    let script = format!(
        "echo $$ > {}; cd -- {} || {{ echo 'Could not enter project directory'; read -r; exit 1; }}; printf '\\033]0;{}\\007'; echo '[BCES] Starting service...'; {}; code=$?; echo; echo \"[BCES] Service stopped with exit code $code\"; echo '[BCES] Press Enter to close this terminal.'; read -r _; exit $code",
        shell_quote(&pid_file.to_string_lossy()),
        shell_quote(&cwd.to_string_lossy()),
        title.replace('\'', ""),
        command,
    );

    let mut terminal_command = TokioCommand::new(&terminal);
    match executable_name {
        "gnome-terminal" => {
            terminal_command.args(["--wait", "--title", title, "--", "bash", "-lc", &script]);
        }
        "kgx" => {
            terminal_command.args(["--title", title, "--", "bash", "-lc", &script]);
        }
        "terminator" => {
            terminal_command.args(["-T", title, "-x", "bash", "-lc", &script]);
        }
        "konsole" => {
            terminal_command.args([
                "--separate",
                "--nofork",
                "--title",
                title,
                "-e",
                "bash",
                "-lc",
                &script,
            ]);
        }
        "xfce4-terminal" => {
            let command_arg = format!("bash -lc {}", shell_quote(&script));
            terminal_command.args([
                "--disable-server",
                "--title",
                title,
                "--command",
                &command_arg,
            ]);
        }
        "mate-terminal" => {
            terminal_command.args([
                "--disable-factory",
                "--title",
                title,
                "--",
                "bash",
                "-lc",
                &script,
            ]);
        }
        "lxterminal" => {
            terminal_command.args([
                "--no-remote",
                "--title",
                title,
                "-e",
                "bash",
                "-lc",
                &script,
            ]);
        }
        "kitty" => {
            terminal_command.args(["--title", title, "bash", "-lc", &script]);
        }
        "alacritty" => {
            terminal_command.args(["--title", title, "-e", "bash", "-lc", &script]);
        }
        "foot" => {
            terminal_command.args(["--title", title, "bash", "-lc", &script]);
        }
        _ => {
            // xterm and x-terminal-emulator compatible syntax.
            terminal_command.args(["-T", title, "-e", "bash", "-lc", &script]);
        }
    }

    terminal_command
        .spawn()
        .with_context(|| format!("Could not start terminal emulator {}", terminal.display()))
}

#[cfg(target_os = "linux")]
fn find_linux_terminal() -> Option<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(value) = env::var("TERMINAL") {
        if !value.trim().is_empty() {
            candidates.push(value);
        }
    }
    candidates.extend([
        "gnome-terminal".to_string(),
        "kgx".to_string(),
        "konsole".to_string(),
        "xfce4-terminal".to_string(),
        "mate-terminal".to_string(),
        "lxterminal".to_string(),
        "kitty".to_string(),
        "alacritty".to_string(),
        "foot".to_string(),
        "xterm".to_string(),
        "terminator".to_string(),
        "x-terminal-emulator".to_string(),
    ]);

    for candidate in candidates {
        let output = match Command::new("sh")
            .args(["-lc", &format!("command -v {}", shell_quote(&candidate))])
            .output()
        {
            Ok(output) => output,
            Err(_) => continue,
        };
        if output.status.success() {
            let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !path.is_empty() {
                return Some(PathBuf::from(path));
            }
        }
    }
    None
}

#[cfg(target_os = "linux")]
fn shell_quote(value: &str) -> String {
    format!("'{}'", value.replace('\'', "'\\''"))
}

#[cfg(target_os = "linux")]
async fn read_pid_file(path: &Path) -> Option<u32> {
    for _ in 0..40 {
        if let Ok(contents) = fs::read_to_string(path) {
            if let Ok(pid) = contents.trim().parse::<u32>() {
                return Some(pid);
            }
        }
        sleep(Duration::from_millis(50)).await;
    }
    None
}

#[cfg(windows)]
fn ps_quote(path: &Path) -> String {
    // canonicalize() may return extended-length paths (\\?\A:\project).
    // PowerShell accepts them, but npm.cmd delegates to cmd.exe, which does not.
    let raw = path.to_string_lossy();
    let normalized = if let Some(rest) = raw.strip_prefix(r"\\?\UNC\") {
        format!(r"\\{}", rest)
    } else if let Some(rest) = raw.strip_prefix(r"\\?\") {
        rest.to_string()
    } else {
        raw.into_owned()
    };

    format!("'{}'", normalized.replace('\'', "''"))
}

#[cfg(windows)]
fn spawn_windows_console(script: &str) -> Result<Child> {
    use std::os::windows::process::CommandExt;
    const CREATE_NEW_CONSOLE: u32 = 0x00000010;

    let mut command = TokioCommand::new("powershell.exe");
    command.args([
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-NoExit",
        "-Command",
        script,
    ]);
    command.as_std_mut().creation_flags(CREATE_NEW_CONSOLE);
    command
        .spawn()
        .context("Could not create a new PowerShell console")
}

#[cfg(all(unix, not(target_os = "linux")))]
fn configure_process_group(command: &mut TokioCommand) {
    use std::os::unix::process::CommandExt;
    command.as_std_mut().process_group(0);
}

#[cfg(target_os = "linux")]
async fn terminate_child(child: &mut Child, shell_pid: Option<u32>) {
    if let Some(pid) = shell_pid {
        terminate_process_tree(pid);
    }
    if let Some(pid) = child.id() {
        let _ = Command::new("kill")
            .args(["-TERM", &pid.to_string()])
            .status();
        tokio::time::sleep(Duration::from_millis(500)).await;
        let _ = Command::new("kill")
            .args(["-KILL", &pid.to_string()])
            .status();
    }
    let _ = child.wait().await;
}

#[cfg(all(unix, not(target_os = "linux")))]
async fn terminate_child(child: &mut Child, _shell_pid: Option<u32>) {
    if let Some(pid) = child.id() {
        let _ = Command::new("kill")
            .args(["-TERM", "--", &format!("-{pid}")])
            .status();
        sleep(Duration::from_secs(2)).await;
        let _ = Command::new("kill")
            .args(["-KILL", "--", &format!("-{pid}")])
            .status();
    }
    let _ = child.wait().await;
}

#[cfg(windows)]
async fn terminate_child(child: &mut Child, _shell_pid: Option<u32>) {
    if let Some(pid) = child.id() {
        let _ = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .status();
    }
    let _ = child.wait().await;
}

#[cfg(target_os = "linux")]
fn terminate_process_tree(pid: u32) {
    fn collect(pid: u32, result: &mut Vec<u32>) {
        let output = Command::new("pgrep")
            .args(["-P", &pid.to_string()])
            .output();
        if let Ok(output) = output {
            for line in String::from_utf8_lossy(&output.stdout).lines() {
                if let Ok(child_pid) = line.trim().parse::<u32>() {
                    collect(child_pid, result);
                    result.push(child_pid);
                }
            }
        }
    }

    let mut descendants = Vec::new();
    collect(pid, &mut descendants);
    for child_pid in &descendants {
        let _ = Command::new("kill")
            .args(["-TERM", &child_pid.to_string()])
            .status();
    }
    let _ = Command::new("kill")
        .args(["-TERM", &pid.to_string()])
        .status();
    std::thread::sleep(Duration::from_millis(500));
    for child_pid in descendants {
        let _ = Command::new("kill")
            .args(["-KILL", &child_pid.to_string()])
            .status();
    }
    let _ = Command::new("kill")
        .args(["-KILL", &pid.to_string()])
        .status();
}

async fn pipe_logs(
    stdout: Option<tokio::process::ChildStdout>,
    stderr: Option<tokio::process::ChildStderr>,
    label: &'static str,
) {
    let mut tasks = Vec::new();

    if let Some(stdout) = stdout {
        tasks.push(tokio::spawn(async move {
            let mut lines = AsyncBufReader::new(stdout).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                println!("[{label}] {line}");
            }
        }));
    }

    if let Some(stderr) = stderr {
        tasks.push(tokio::spawn(async move {
            let mut lines = AsyncBufReader::new(stderr).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                eprintln!("[{label}] {line}");
            }
        }));
    }

    for task in tasks {
        let _ = task.await;
    }
}

fn check_port(port: u16) -> Result<()> {
    let address = format!("127.0.0.1:{port}");
    let listener = std::net::TcpListener::bind(&address)
        .with_context(|| format!("Port {port} is already in use"))?;
    drop(listener);
    Ok(())
}

fn save_state(path: &Path, state: &State) -> Result<()> {
    let json = serde_json::to_vec_pretty(state)?;
    fs::write(path, json)?;
    Ok(())
}

fn load_state(path: &Path) -> State {
    fs::read(path)
        .ok()
        .and_then(|bytes| serde_json::from_slice(&bytes).ok())
        .unwrap_or_default()
}

fn ensure_not_running(paths: &Paths) -> Result<()> {
    let state = load_state(&paths.state);
    if state.backend_pid.is_some() || state.frontend_pid.is_some() {
        // A stale state file is harmless if the PIDs no longer exist.
        let backend_alive = state.backend_pid.map(pid_alive).unwrap_or(false);
        let frontend_alive = state.frontend_pid.map(pid_alive).unwrap_or(false);
        let backend_shell_alive = state.backend_shell_pid.map(pid_alive).unwrap_or(false);
        let frontend_shell_alive = state.frontend_shell_pid.map(pid_alive).unwrap_or(false);
        if backend_alive || frontend_alive || backend_shell_alive || frontend_shell_alive {
            bail!("A launcher instance appears to be running. Run `bces-dev stop` first.");
        }
        let _ = fs::remove_file(&paths.state);
    }
    Ok(())
}

fn pid_alive(pid: u32) -> bool {
    if cfg!(windows) {
        Command::new("tasklist")
            .args(["/FI", &format!("PID eq {pid}"), "/FO", "CSV", "/NH"])
            .output()
            .map(|output| {
                String::from_utf8_lossy(&output.stdout).lines().any(|line| {
                    let fields: Vec<&str> = line.trim().trim_matches('"').split("\",\"").collect();
                    fields
                        .get(1)
                        .and_then(|value| value.trim_matches('"').parse::<u32>().ok())
                        == Some(pid)
                })
            })
            .unwrap_or(false)
    } else {
        Command::new("kill")
            .args(["-0", &pid.to_string()])
            .status()
            .map(|status| status.success())
            .unwrap_or(false)
    }
}

fn stop(paths: &Paths) -> Result<()> {
    let state = load_state(&paths.state);
    let mut found = false;

    for (name, pid, group, shell_pid) in [
        (
            "frontend",
            state.frontend_pid,
            state.frontend_group.unwrap_or(!cfg!(windows)),
            state.frontend_shell_pid,
        ),
        (
            "backend",
            state.backend_pid,
            state.backend_group.unwrap_or(!cfg!(windows)),
            state.backend_shell_pid,
        ),
    ] {
        if let Some(pid) = pid {
            found = true;
            println!("[BCES] Stopping {name} (PID {pid})...");
            terminate_pid(pid, group, shell_pid);
        }
    }

    let _ = fs::remove_file(&paths.state);
    let _ = fs::remove_file(&paths.backend_pid_file);
    let _ = fs::remove_file(&paths.frontend_pid_file);

    if !found {
        println!("[BCES] No launcher-managed processes found.");
    } else {
        println!("[BCES] Stop signal sent.");
    }
    Ok(())
}

fn terminate_pid(pid: u32, group: bool, shell_pid: Option<u32>) {
    #[cfg(windows)]
    {
        let _ = (group, shell_pid);
        let _ = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .status();
    }
    #[cfg(target_os = "linux")]
    {
        let _ = group;
        if let Some(shell_pid) = shell_pid {
            terminate_process_tree(shell_pid);
        }
        let _ = Command::new("kill")
            .args(["-TERM", &pid.to_string()])
            .status();
        std::thread::sleep(Duration::from_millis(500));
        let _ = Command::new("kill")
            .args(["-KILL", &pid.to_string()])
            .status();
    }
    #[cfg(all(unix, not(target_os = "linux")))]
    {
        let _ = shell_pid;
        if group {
            let _ = Command::new("kill")
                .args(["-TERM", "--", &format!("-{pid}")])
                .status();
            std::thread::sleep(Duration::from_secs(2));
            let _ = Command::new("kill")
                .args(["-KILL", "--", &format!("-{pid}")])
                .status();
        } else {
            let _ = Command::new("kill")
                .args(["-TERM", &pid.to_string()])
                .status();
        }
    }
}

fn status(paths: &Paths) -> Result<()> {
    let state = load_state(&paths.state);
    print_status("Backend", state.backend_pid);
    print_status("Frontend", state.frontend_pid);
    Ok(())
}

fn print_status(name: &str, pid: Option<u32>) {
    match pid {
        Some(pid) if pid_alive(pid) => println!("[RUNNING] {name} (PID {pid})"),
        Some(pid) => println!("[STOPPED] {name} (stale PID {pid})"),
        None => println!("[STOPPED] {name}"),
    }
}
