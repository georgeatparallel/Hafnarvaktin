/**
 * Container runtime abstraction for NanoClaw.
 * All runtime-specific logic lives here so swapping runtimes means changing one file.
 */
import { execSync } from 'child_process';
import os from 'os';

import { CONTAINER_INSTALL_LABEL } from './config.js';
import { log } from './log.js';

/** The container runtime binary name. */
export const CONTAINER_RUNTIME_BIN = 'docker';

/**
 * Detect rootless Docker. Cached after first call.
 *
 * Under rootless Docker the daemon runs as the invoking user, and the
 * container's user namespace maps host UID (the daemon's UID) to container
 * UID 0. So bind-mounted files owned by the host user appear as root inside
 * the container, and `--user $hostUid:$hostGid` does NOT match the file
 * owner — it maps to a sub-UID instead. The right value for rootless is
 * `--user 0:0`, so container-root maps back to the host user.
 */
let _isRootlessDocker: boolean | null = null;
export function isRootlessDocker(): boolean {
  if (_isRootlessDocker !== null) return _isRootlessDocker;
  try {
    const out = execSync(`${CONTAINER_RUNTIME_BIN} info --format '{{json .SecurityOptions}}'`, {
      encoding: 'utf-8',
      timeout: 5000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    _isRootlessDocker = /\brootless\b/i.test(out);
  } catch {
    _isRootlessDocker = false;
  }
  return _isRootlessDocker;
}

/** CLI args needed for the container to resolve the host gateway. */
export function hostGatewayArgs(): string[] {
  // On Linux, host.docker.internal isn't built-in — add it explicitly
  if (os.platform() === 'linux') {
    return ['--add-host=host.docker.internal:host-gateway'];
  }
  return [];
}

/**
 * Rootless-Docker network bridge for OneCLI.
 *
 * Under rootless Docker, the OneCLI container sits on its own bridge network
 * and publishes ports onto the rootful docker0 IP (172.17.0.1) — but rootless
 * Docker has its OWN 172.17.0.1 inside slirp4netns, with no listener there.
 * So agent containers spawned with `host.docker.internal:host-gateway` can't
 * reach OneCLI at all.
 *
 * Workaround: attach the agent container to OneCLI's bridge network and
 * alias `host.docker.internal` directly to OneCLI's IP on that network. The
 * OneCLI container is conventionally named `onecli` (per its compose stack).
 *
 * Returns null if not rootless, or if OneCLI can't be discovered — caller
 * falls back to the standard hostGatewayArgs().
 */
let _rootlessOnecliNetwork: { network: string; ip: string } | null | undefined;
export function rootlessOnecliBridgeArgs(): string[] | null {
  if (!isRootlessDocker()) return null;
  if (_rootlessOnecliNetwork === undefined) {
    _rootlessOnecliNetwork = null;
    try {
      const out = execSync(`${CONTAINER_RUNTIME_BIN} inspect onecli --format '{{json .NetworkSettings.Networks}}'`, {
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 5000,
      });
      const networks = JSON.parse(out) as Record<string, { IPAddress?: string }>;
      for (const [name, cfg] of Object.entries(networks)) {
        if (cfg?.IPAddress) {
          _rootlessOnecliNetwork = { network: name, ip: cfg.IPAddress };
          break;
        }
      }
    } catch (err) {
      log.warn('Failed to discover OneCLI network for rootless bridge', { err });
    }
  }
  if (!_rootlessOnecliNetwork) return null;
  return ['--network', _rootlessOnecliNetwork.network, `--add-host=host.docker.internal:${_rootlessOnecliNetwork.ip}`];
}

/** Returns CLI args for a readonly bind mount. */
export function readonlyMountArgs(hostPath: string, containerPath: string): string[] {
  return ['-v', `${hostPath}:${containerPath}:ro`];
}

/** Stop a container by name. Uses execFileSync to avoid shell injection. */
export function stopContainer(name: string): void {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/.test(name)) {
    throw new Error(`Invalid container name: ${name}`);
  }
  execSync(`${CONTAINER_RUNTIME_BIN} stop -t 1 ${name}`, { stdio: 'pipe' });
}

/** Ensure the container runtime is running, starting it if needed. */
export function ensureContainerRuntimeRunning(): void {
  try {
    execSync(`${CONTAINER_RUNTIME_BIN} info`, {
      stdio: 'pipe',
      timeout: 10000,
    });
    log.debug('Container runtime already running');
  } catch (err) {
    log.error('Failed to reach container runtime', { err });
    console.error('\n╔════════════════════════════════════════════════════════════════╗');
    console.error('║  FATAL: Container runtime failed to start                      ║');
    console.error('║                                                                ║');
    console.error('║  Agents cannot run without a container runtime. To fix:        ║');
    console.error('║  1. Ensure Docker is installed and running                     ║');
    console.error('║  2. Run: docker info                                           ║');
    console.error('║  3. Restart NanoClaw                                           ║');
    console.error('╚════════════════════════════════════════════════════════════════╝\n');
    throw new Error('Container runtime is required but failed to start', {
      cause: err,
    });
  }
}

/**
 * Kill orphaned NanoClaw containers from THIS install's previous runs.
 *
 * Scoped by label `nanoclaw-install=<slug>` so a crash-looping peer install
 * cannot reap our containers, and we cannot reap theirs. The label is
 * stamped onto every container at spawn time — see container-runner.ts.
 */
export function cleanupOrphans(): void {
  try {
    const output = execSync(
      `${CONTAINER_RUNTIME_BIN} ps --filter label=${CONTAINER_INSTALL_LABEL} --format '{{.Names}}'`,
      {
        stdio: ['pipe', 'pipe', 'pipe'],
        encoding: 'utf-8',
      },
    );
    const orphans = output.trim().split('\n').filter(Boolean);
    for (const name of orphans) {
      try {
        stopContainer(name);
      } catch {
        /* already stopped */
      }
    }
    if (orphans.length > 0) {
      log.info('Stopped orphaned containers', { count: orphans.length, names: orphans });
    }
  } catch (err) {
    log.warn('Failed to clean up orphaned containers', { err });
  }
}
