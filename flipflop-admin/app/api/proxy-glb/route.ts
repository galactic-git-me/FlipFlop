export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const url = searchParams.get('url');

  if (!url) {
    return new Response('Missing url parameter', { status: 400 });
  }

  try {
    const response = await fetch(url);
    if (!response.ok) {
      return new Response('Failed to fetch GLB', { status: response.status });
    }

    // Pass the upstream body through as a stream. Catalogue models can be
    // hundreds of megabytes; buffering the whole GLB here needlessly doubles
    // memory use before the browser's GLTFLoader can read it.
    return new Response(response.body, {
      headers: {
        'Content-Type': response.headers.get('content-type') || 'model/gltf-binary',
        ...(response.headers.get('content-length') ? { 'Content-Length': response.headers.get('content-length')! } : {}),
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (error) {
    console.error('Proxy error:', error);
    return new Response('Proxy error', { status: 500 });
  }
}
