#!/usr/bin/env python3
"""
Test script for authentication API endpoints.
Tests signup, login, and get current user functionality.
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api"

# Test data
TEST_USER = {
    "email": "test_auth@example.com",
    "password": "SecurePassword123",
    "name": "Test User",
}

DUPLICATE_USER = {
    "email": "test_auth@example.com",
    "password": "DifferentPassword456",
    "name": "Duplicate User",
}

INVALID_LOGIN = {
    "email": "test_auth@example.com",
    "password": "WrongPassword",
}

async def test_auth_endpoints():
    """Test all authentication endpoints."""
    async with httpx.AsyncClient(timeout=30) as client:
        print("=" * 60)
        print("FlipFlop Authentication API Tests")
        print("=" * 60)

        # Test 1: Signup
        print("\n[TEST 1] Signup with new user")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/signup",
                json=TEST_USER
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")

            if response.status_code != 201:
                print("✗ FAILED: Expected 201, got", response.status_code)
                return False

            signup_data = response.json()
            if "access_token" not in signup_data:
                print("✗ FAILED: No access_token in response")
                return False

            access_token = signup_data["access_token"]
            print("✓ PASSED: Signup successful, token received")

        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False

        # Test 2: Duplicate signup (should fail)
        print("\n[TEST 2] Signup with duplicate email (should fail)")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/signup",
                json=DUPLICATE_USER
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")

            if response.status_code != 409:
                print("✗ FAILED: Expected 409, got", response.status_code)
                return False

            print("✓ PASSED: Duplicate email rejected with 409")

        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False

        # Test 3: Login with correct credentials
        print("\n[TEST 3] Login with correct credentials")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/login",
                json={
                    "email": TEST_USER["email"],
                    "password": TEST_USER["password"],
                }
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")

            if response.status_code != 200:
                print("✗ FAILED: Expected 200, got", response.status_code)
                return False

            login_data = response.json()
            if "access_token" not in login_data:
                print("✗ FAILED: No access_token in response")
                return False

            login_token = login_data["access_token"]
            print("✓ PASSED: Login successful, new token received")

        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False

        # Test 4: Login with wrong password (should fail)
        print("\n[TEST 4] Login with wrong password (should fail)")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/login",
                json=INVALID_LOGIN
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")

            if response.status_code != 401:
                print("✗ FAILED: Expected 401, got", response.status_code)
                return False

            print("✓ PASSED: Invalid credentials rejected with 401")

        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False

        # Test 5: Get current user with valid token
        print("\n[TEST 5] Get current user with valid token")
        try:
            response = await client.get(
                f"{BASE_URL}/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")

            if response.status_code != 200:
                print("✗ FAILED: Expected 200, got", response.status_code)
                return False

            user_data = response.json()
            if user_data["email"] != TEST_USER["email"]:
                print("✗ FAILED: Email mismatch in response")
                return False

            if user_data["name"] != TEST_USER["name"]:
                print("✗ FAILED: Name mismatch in response")
                return False

            print("✓ PASSED: Current user retrieved successfully")

        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False

        # Test 6: Get current user with invalid token (should fail)
        print("\n[TEST 6] Get current user with invalid token (should fail)")
        try:
            response = await client.get(
                f"{BASE_URL}/auth/me",
                headers={"Authorization": "Bearer invalid.token.here"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")

            if response.status_code != 401:
                print("✗ FAILED: Expected 401, got", response.status_code)
                return False

            print("✓ PASSED: Invalid token rejected with 401")

        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False

        # Test 7: Get current user without authorization header (should fail)
        print("\n[TEST 7] Get current user without token (should fail)")
        try:
            response = await client.get(f"{BASE_URL}/auth/me")
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")

            if response.status_code != 401:
                print("✗ FAILED: Expected 401, got", response.status_code)
                return False

            print("✓ PASSED: Missing token rejected with 401")

        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False

        return True


async def main():
    """Run all tests."""
    print("\nWaiting for server to be ready...")
    print("Make sure the server is running at http://localhost:8000/api")
    print("\nStarting tests in 2 seconds...\n")
    await asyncio.sleep(2)

    success = await test_auth_endpoints()

    print("\n" + "=" * 60)
    if success:
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
