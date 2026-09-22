self.__BUILD_MANIFEST = {
  "__rewrites": {
    "afterFiles": [
      {
        "source": "/api/gem-radar/:path*"
      },
      {
        "source": "/api/:path*"
      },
      {
        "source": "/uploads/:path*"
      },
      {
        "source": "/health"
      }
    ],
    "beforeFiles": [],
    "fallback": []
  },
  "sortedPages": [
    "/_app",
    "/_error"
  ]
};self.__BUILD_MANIFEST_CB && self.__BUILD_MANIFEST_CB()