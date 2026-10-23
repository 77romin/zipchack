def complete_chat(app):
    # AppTest는 브라우저의 fragment 타이머를 자동 진행하지 않으므로 완료 후 한 번 실행한다.
    if 'housing_job' in app.session_state:
        app.session_state['housing_job']['future'].result(timeout=20)
        app.run()
    return app
