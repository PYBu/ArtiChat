const packages = [
	'micropip',
	'packaging',
	'requests',
	'beautifulsoup4',
	'numpy',
	'pandas',
	'matplotlib',
	'scikit-learn',
	'scipy',
	'regex',
	'sympy',
	'tiktoken',
	'seaborn',
	'pytz',
	'black',
	'openai',
	'openpyxl'
];

// Pure-Python packages whose wheels must be downloaded from PyPI and saved into
// static/pyodide/ so that the browser can install them offline via micropip.
// Packages already provided by the Pyodide distribution (click, platformdirs,
// typing_extensions, etc.) do NOT need to be listed here.
const pypiPackages = ['black', 'pathspec', 'mypy_extensions', 'pytokens'];
const pypiIndexUrl = (
	process.env.PYODIDE_PYPI_INDEX_URL ||
	process.env.PIP_INDEX_URL ||
	'https://pypi.org/simple'
).replace(/\/+$/, '');

import { loadPyodide } from 'pyodide';
import { setGlobalDispatcher, ProxyAgent } from 'undici';
import { writeFile, readFile, copyFile, readdir, rmdir, access } from 'fs/promises';

/**
 * Loading network proxy configurations from the environment variables.
 * And the proxy config with lowercase name has the highest priority to use.
 */
function initNetworkProxyFromEnv() {
	// we assume all subsequent requests in this script are HTTPS:
	// https://cdn.jsdelivr.net
	// https://pypi.org
	// https://files.pythonhosted.org
	const allProxy = process.env.all_proxy || process.env.ALL_PROXY;
	const httpsProxy = process.env.https_proxy || process.env.HTTPS_PROXY;
	const httpProxy = process.env.http_proxy || process.env.HTTP_PROXY;
	const preferedProxy = httpsProxy || allProxy || httpProxy;
	/**
	 * use only http(s) proxy because socks5 proxy is not supported currently:
	 * @see https://github.com/nodejs/undici/issues/2224
	 */
	if (!preferedProxy || !preferedProxy.startsWith('http')) return;
	let preferedProxyURL;
	try {
		preferedProxyURL = new URL(preferedProxy).toString();
	} catch {
		console.warn(`Invalid network proxy URL: "${preferedProxy}"`);
		return;
	}
	const dispatcher = new ProxyAgent({ uri: preferedProxyURL });
	setGlobalDispatcher(dispatcher);
	console.log(`Initialized network proxy "${preferedProxy}" from env`);
}

async function fetchWithRetry(url, attempts = 5) {
	let lastError;
	for (let attempt = 1; attempt <= attempts; attempt += 1) {
		try {
			const response = await fetch(url);
			if (response.ok || response.status < 500) return response;
			lastError = new Error(`HTTP ${response.status} for ${url}`);
		} catch (error) {
			lastError = error;
		}
		if (attempt < attempts) {
			await new Promise((resolve) => setTimeout(resolve, attempt * 2000));
		}
	}
	throw lastError;
}

async function installPackage(micropip, pkg) {
	let lastError;
	for (let attempt = 1; attempt <= 3; attempt += 1) {
		try {
			await micropip.install(pkg);
			return;
		} catch (error) {
			lastError = error;
			if (attempt < 3) {
				console.warn(`Retrying ${pkg} after package download failure (${attempt}/3)`);
				await new Promise((resolve) => setTimeout(resolve, attempt * 3000));
			}
		}
	}
	throw lastError;
}

async function downloadPackages() {
	console.log('Setting up pyodide + micropip');

	let pyodide;
	try {
		pyodide = await loadPyodide({
			packageCacheDir: 'static/pyodide'
		});
	} catch (err) {
		console.error('Failed to load Pyodide:', err);
		return;
	}

	const installedPyodidePackageJson = JSON.parse(
		await readFile('node_modules/pyodide/package.json')
	);
	const pyodideVersion = installedPyodidePackageJson.version;

	try {
		const pyodidePackageJson = JSON.parse(await readFile('static/pyodide/package.json'));
		const pyodidePackageVersion = pyodidePackageJson.version.replace('^', '');

		if (pyodideVersion !== pyodidePackageVersion) {
			console.log('Pyodide version mismatch, removing static/pyodide directory');
			await rmdir('static/pyodide', { recursive: true });
		}
	} catch (err) {
		console.log('Pyodide package not found, proceeding with download.', err);
	}

	try {
		console.log('Loading micropip package');
		await pyodide.loadPackage('micropip');

		const micropip = pyodide.pyimport('micropip');
		console.log('Downloading Pyodide packages:', packages);

		try {
			for (const pkg of packages) {
				console.log(`Installing package: ${pkg}`);
				await installPackage(micropip, pkg);
			}
		} catch (err) {
			console.error('Package installation failed:', err);
			return;
		}

		console.log('Pyodide packages downloaded, freezing into lock file');

		try {
			const lockFile = await micropip.freeze();
			await writeFile('static/pyodide/pyodide-lock.json', lockFile);
		} catch (err) {
			console.error('Failed to write lock file:', err);
		}
	} catch (err) {
		console.error('Failed to load or install micropip:', err);
	}
}

async function findPurePythonWheel(pkg) {
	const response = await fetchWithRetry(`${pypiIndexUrl}/${pkg}/`);
	if (!response.ok) {
		console.error(`Failed to fetch PyPI index for ${pkg}: ${response.status}`);
		return null;
	}

	const html = await response.text();
	const links = [...html.matchAll(/href=["']([^"']+\.whl(?:#[^"']*)?)["']/gi)];
	const normalizedPackage = pkg.toLowerCase().replace(/[-_.]+/g, '-');
	const wheels = links
		.map((match) => {
			const url = new URL(match[1].replaceAll('&amp;', '&'), `${pypiIndexUrl}/${pkg}/`);
			const filename = decodeURIComponent(url.pathname.split('/').at(-1) || '');
			const normalizedFilename = filename.toLowerCase().replace(/[-_.]+/g, '-');
			if (
				!normalizedFilename.startsWith(`${normalizedPackage}-`) ||
				!filename.endsWith('py3-none-any.whl')
			) {
				return null;
			}
			const version = filename.match(/^[^-]+-([^-]+)-/)?.[1] || '';
			return {
				filename,
				version,
				url: url.toString(),
				sha256: url.hash.startsWith('#sha256=') ? url.hash.slice('#sha256='.length) : ''
			};
		})
		.filter(Boolean);

	return wheels.at(-1) || null;
}

async function copyPyodide() {
	console.log('Copying Pyodide files into static directory');
	// Copy all files from node_modules/pyodide to static/pyodide
	for await (const entry of await readdir('node_modules/pyodide')) {
		await copyFile(`node_modules/pyodide/${entry}`, `static/pyodide/${entry}`);
	}
}

/**
 * Download pure-Python wheels from PyPI and save them into static/pyodide/.
 * Also injects entries into pyodide-lock.json so that micropip resolves these
 * packages from the local server instead of fetching them from the internet.
 */
async function downloadPyPIWheels() {
	const lockPath = 'static/pyodide/pyodide-lock.json';
	let lockData;
	try {
		lockData = JSON.parse(await readFile(lockPath, 'utf-8'));
	} catch {
		console.warn('Could not read pyodide-lock.json, skipping PyPI wheel download');
		return;
	}

	for (const pkg of pypiPackages) {
		console.log(`Fetching PyPI metadata for: ${pkg}`);
		const wheel = await findPurePythonWheel(pkg);
		if (!wheel) {
			console.warn(`No pure-Python wheel found for ${pkg}, skipping`);
			continue;
		}
		const version = wheel.version;
		const dest = `static/pyodide/${wheel.filename}`;
		// Download wheel if not already present
		try {
			await access(dest);
			console.log(`  Already exists: ${wheel.filename}`);
		} catch {
			console.log(`  Downloading: ${wheel.filename}`);
			const wheelRes = await fetchWithRetry(wheel.url);
			if (!wheelRes.ok) {
				console.error(`  Failed to download ${wheel.filename}: ${wheelRes.status}`);
				continue;
			}
			const buffer = Buffer.from(await wheelRes.arrayBuffer());
			await writeFile(dest, buffer);
			console.log(`  Saved: ${dest} (${buffer.length} bytes)`);
		}

		// Inject into pyodide-lock.json so micropip resolves locally
		const normalizedName = pkg.replace(/-/g, '_');
		if (!lockData.packages[normalizedName]) {
			lockData.packages[normalizedName] = {
				name: normalizedName,
				version: version,
				file_name: wheel.filename,
				install_dir: 'site',
				sha256: wheel.sha256,
				package_type: 'package',
				imports: [normalizedName],
				depends: []
			};
			console.log(`  Added ${normalizedName}==${version} to pyodide-lock.json`);
		}
	}

	await writeFile(lockPath, JSON.stringify(lockData, null, 2));
	console.log('Updated pyodide-lock.json with PyPI packages');
}

initNetworkProxyFromEnv();
await downloadPackages();
await copyPyodide();
await downloadPyPIWheels();
