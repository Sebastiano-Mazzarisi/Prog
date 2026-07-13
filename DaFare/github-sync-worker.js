const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Accept"
};

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      if (request.method === "GET") {
        return await readData(env);
      }

      if (request.method === "PUT") {
        const data = await request.json();
        return await writeData(env, data);
      }

      return json({ error: "Metodo non supportato" }, 405);
    } catch (error) {
      return json({ error: error.message }, 500);
    }
  }
};

async function readData(env) {
  const response = await fetch(githubContentUrl(env, true), {
    headers: githubHeaders(env)
  });

  if (response.status === 404) {
    return json({
      version: 1,
      updatedAt: 0,
      updatedBy: "",
      notes: []
    });
  }

  if (!response.ok) {
    throw new Error("GitHub read " + response.status);
  }

  const file = await response.json();
  return json(JSON.parse(decodeBase64(file.content || "")));
}

async function writeData(env, data) {
  const current = await fetch(githubContentUrl(env, true), {
    headers: githubHeaders(env)
  });

  let sha = null;
  if (current.ok) {
    const file = await current.json();
    sha = file.sha;
  } else if (current.status !== 404) {
    throw new Error("GitHub read " + current.status);
  }

  const body = {
    message: "Aggiorna cose da fare",
    content: encodeBase64(JSON.stringify(data, null, 2)),
    branch: env.GITHUB_BRANCH || "main"
  };

  if (sha) {
    body.sha = sha;
  }

  const response = await fetch(githubContentUrl(env, false), {
    method: "PUT",
    headers: {
      ...githubHeaders(env),
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    throw new Error("GitHub write " + response.status);
  }

  return json({ ok: true });
}

function githubContentUrl(env, withRef) {
  const owner = encodeURIComponent(env.GITHUB_OWNER);
  const repo = encodeURIComponent(env.GITHUB_REPO);
  const path = String(env.GITHUB_PATH || "DaFare/todo-priorita-dati.json")
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${path}`;
  return withRef ? `${url}?ref=${encodeURIComponent(env.GITHUB_BRANCH || "main")}` : url;
}

function githubHeaders(env) {
  return {
    "Accept": "application/vnd.github+json",
    "Authorization": "Bearer " + env.GITHUB_TOKEN,
    "User-Agent": "da-fare-sync",
    "X-GitHub-Api-Version": "2022-11-28"
  };
}

function json(data, status) {
  return new Response(JSON.stringify(data), {
    status: status || 200,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json; charset=utf-8"
    }
  });
}

function encodeBase64(text) {
  return btoa(unescape(encodeURIComponent(text)));
}

function decodeBase64(text) {
  return decodeURIComponent(escape(atob(text.replace(/\s/g, ""))));
}
