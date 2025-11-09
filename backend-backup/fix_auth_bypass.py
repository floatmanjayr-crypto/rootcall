# Check if main.py has auth middleware
with open('app/main.py', 'r') as f:
    main_content = f.read()

if 'AuthMiddleware' in main_content or 'authentication' in main_content.lower():
    print("Found auth middleware in main.py")
    # Add webhook to excluded paths
    if 'excluded_paths' in main_content:
        # Find the list and add our webhook
        lines = main_content.split('\n')
        for i, line in enumerate(lines):
            if 'excluded_paths' in line and '[' in line:
                # Found the list, add our path
                if '"/telnyx/badbot/webhook"' not in line:
                    line = line.replace(']', ', "/telnyx/badbot/webhook"]')
                    lines[i] = line
                    print(f"Added webhook to excluded_paths: {line}")
        main_content = '\n'.join(lines)
        
        with open('app/main.py', 'w') as f:
            f.write(main_content)
        print("Updated! Server will reload.")
    else:
        print("No excluded_paths found - showing auth middleware section:")
        for line in main_content.split('\n'):
            if 'middleware' in line.lower() or 'auth' in line.lower():
                print(f"  {line}")
else:
    print("No auth middleware found in main.py")
    print("\nChecking badbot_screen.py...")
    
    with open('app/routers/badbot_screen.py', 'r') as f:
        screen_content = f.read()
    
    # Show the webhook endpoint
    lines = screen_content.split('\n')
    for i, line in enumerate(lines):
        if '@router.post("/webhook"' in line:
            print("Webhook endpoint:")
            for j in range(i, min(i+5, len(lines))):
                print(f"  {lines[j]}")
            break

