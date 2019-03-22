from .graphql_view import GraphQLView

__version__ = '0.1.0'


class GraphQL(object):
    def __init__(self, schema, app=None, **options):
        self.app = app
        self.init_app(app)
        self.graphql_view = GraphQLView(schema=schema, **options)

    def init_app(self, app=None):
        if app:
            self.app = app
        assert self.app, RuntimeError("App object not existed!")

        @self.app.route('/graphql', methods=['GET', 'POST'])
        async def graphql_index(request):
            return self.graphql_view.process_request(request)
