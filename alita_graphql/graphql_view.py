"""
alita graphsql.
install package[graphql-server-core].
"""
from functools import partial
from alita import JsonResponse, render_template_string
from graphql.type.schema import GraphQLSchema
from graphql_server import (HttpQueryError, default_format_error,
                            encode_execution_results, json_encode,
                            load_json_body, run_http_query)


GRAPHIQL_VERSION = '0.11.11'

TEMPLATE = '''<!--
The request to this GraphQL server provided the header "Accept: text/html"
and as a result has been presented GraphiQL - an in-browser IDE for
exploring GraphQL.
If you wish to receive JSON, provide the header "Accept: application/json" or
add "&raw" to the end of the URL within a browser.
-->
<!DOCTYPE html>
<html>
<head>
  <title>{{graphiql_html_title|default("GraphiQL", true)}}</title>
  <style>
    html, body {
      height: 100%;
      margin: 0;
      overflow: hidden;
      width: 100%;
    }
  </style>
  <meta name="referrer" content="no-referrer">
  <link href="//cdn.jsdelivr.net/npm/graphiql@{{graphiql_version}}/graphiql.css" rel="stylesheet" />
  <script src="//cdn.jsdelivr.net/fetch/0.9.0/fetch.min.js"></script>
  <script src="//cdn.jsdelivr.net/react/15.0.0/react.min.js"></script>
  <script src="//cdn.jsdelivr.net/react/15.0.0/react-dom.min.js"></script>
  <script src="//cdn.jsdelivr.net/npm/graphiql@{{graphiql_version}}/graphiql.min.js"></script>
</head>
<body>
  <script>
    // Collect the URL parameters
    var parameters = {};
    window.location.search.substr(1).split('&').forEach(function (entry) {
      var eq = entry.indexOf('=');
      if (eq >= 0) {
        parameters[decodeURIComponent(entry.slice(0, eq))] =
          decodeURIComponent(entry.slice(eq + 1));
      }
    });
    // Produce a Location query string from a parameter object.
    function locationQuery(params) {
      return '?' + Object.keys(params).map(function (key) {
        return encodeURIComponent(key) + '=' +
          encodeURIComponent(params[key]);
      }).join('&');
    }
    // Derive a fetch URL from the current URL, sans the GraphQL parameters.
    var graphqlParamNames = {
      query: true,
      variables: true,
      operationName: true
    };
    var otherParams = {};
    for (var k in parameters) {
      if (parameters.hasOwnProperty(k) && graphqlParamNames[k] !== true) {
        otherParams[k] = parameters[k];
      }
    }
    var fetchURL = locationQuery(otherParams);
    // Defines a GraphQL fetcher using the fetch API.
    function graphQLFetcher(graphQLParams) {
      return fetch(fetchURL, {
        method: 'post',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(graphQLParams),
        credentials: 'include',
      }).then(function (response) {
        return response.text();
      }).then(function (responseBody) {
        try {
          return JSON.parse(responseBody);
        } catch (error) {
          return responseBody;
        }
      });
    }
    // When the query and variables string is edited, update the URL bar so
    // that it can be easily shared.
    function onEditQuery(newQuery) {
      parameters.query = newQuery;
      updateURL();
    }
    function onEditVariables(newVariables) {
      parameters.variables = newVariables;
      updateURL();
    }
    function onEditOperationName(newOperationName) {
      parameters.operationName = newOperationName;
      updateURL();
    }
    function updateURL() {
      history.replaceState(null, null, locationQuery(parameters));
    }
    // Render <GraphiQL /> into the body.
    ReactDOM.render(
      React.createElement(GraphiQL, {
        fetcher: graphQLFetcher,
        onEditQuery: onEditQuery,
        onEditVariables: onEditVariables,
        onEditOperationName: onEditOperationName,
        query: {{ params.query|tojson }},
        response: {{ result|tojson }},
        variables: {{ params.variables|tojson }},
        operationName: {{ params.operation_name|tojson }},
      }),
      document.body
    );
  </script>
</body>
</html>'''


def render_graphiql(request, params, result, graphiql_version=None,
                    graphiql_template=None, graphiql_html_title=None):
    graphiql_version = graphiql_version or GRAPHIQL_VERSION
    template = graphiql_template or TEMPLATE

    return render_template_string(
        request,
        template,
        graphiql_version=graphiql_version,
        graphiql_html_title=graphiql_html_title,
        result=result,
        params=params
    )


class GraphQLView(object):
    schema = None
    executor = None
    root_value = None
    pretty = False
    graphiql = False
    backend = None
    graphiql_version = None
    graphiql_template = None
    graphiql_html_title = None
    middleware = None
    batch = False

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        assert isinstance(self.schema, GraphQLSchema), 'A Schema is required to be provided to GraphQLView.'

    def get_root_value(self):
        return self.root_value

    def get_middleware(self):
        return self.middleware

    def get_backend(self):
        return self.backend

    def get_executor(self):
        return self.executor

    def render_graphiql(self, request, params, result):
        return render_graphiql(
            request=request,
            params=params,
            result=result,
            graphiql_version=self.graphiql_version,
            graphiql_template=self.graphiql_template,
            graphiql_html_title=self.graphiql_html_title,
        )

    format_error = staticmethod(default_format_error)
    encode = staticmethod(json_encode)

    def process_request(self, request):
        try:
            request_method = request.method.lower()
            data = self.parse_body(request)
            if data.get("operationName") == 'undefined':
                data['operationName'] = None
            if request.args.get('operationName') == 'undefined':
                request.args['operationName'] = None

            catch = show_graphiql = self.should_display_graphiql(request)
            pretty = self.pretty or show_graphiql or request.args.get('pretty')

            extra_options = {}
            executor = self.get_executor()
            if executor:
                # We only include it optionally since
                # executor is not a valid argument in all backends
                extra_options['executor'] = executor

            execution_results, all_params = run_http_query(
                self.schema,
                request_method,
                data,
                query_data=request.args,
                batch_enabled=self.batch,
                catch=catch,
                backend=self.get_backend(),

                # Execute options
                root=self.get_root_value(),
                context=request,
                middleware=self.get_middleware(),
                **extra_options
            )
            result, status_code = encode_execution_results(
                execution_results,
                is_batch=isinstance(data, list),
                format_error=self.format_error,
                encode=partial(self.encode, pretty=pretty)
            )

            if show_graphiql:
                return self.render_graphiql(
                    request=request,
                    params=all_params[0],
                    result=result
                )

            return JsonResponse(
                result,
                status=status_code,
                content_type='application/json'
            )

        except HttpQueryError as e:
            return JsonResponse({
                    'errors': [self.format_error(e)]
                },
                status=e.status_code,
                headers=e.headers,
                content_type='application/json'
            )

    def parse_body(self, request):
        content_type = request.content_type
        if content_type == 'application/graphql':
            return {'query': request.data}

        elif content_type == 'application/json':
            return load_json_body(request.data)

        elif content_type in ('application/x-www-form-urlencoded', 'multipart/form-data'):
            return request.form

        return {}

    def should_display_graphiql(self, request):
        return request.method.lower() == 'get' and \
               not self.graphiql or 'raw' in request.args
