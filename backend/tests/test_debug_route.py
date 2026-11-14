import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import rootcall_screen


class DebugRouteTests(unittest.TestCase):
    def test_public_debug_route_does_not_expose_customer_numbers(self):
        app = FastAPI()
        app.include_router(rootcall_screen.router)
        body = TestClient(app).get("/telnyx/rootcall/debug").json()
        self.assertNotIn("telnyx_numbers", body)
        self.assertNotIn("client_count", body)
