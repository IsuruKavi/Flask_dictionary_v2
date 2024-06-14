from flask import Flask, jsonify
import json
app = Flask(__name__)

@app.route('/', methods=['GET'])
def get_data():
     #Encode the data with the ensure_ascii parameter set to False
    # json_data = json.dumps(data, ensure_ascii=False)
    data1 = {'message': "මේක ප්ලැයි"}

    data=json.dumps(data1,ensure_ascii=False)
    return data

if __name__ == '__main__':
    app.run(debug=True)


# response_json = '{"message": "\\u0db8\\u0dda\\u0d9a \\u0db4\\u0dca\\u0dbd\\u0dd0\\u0dba\\u0dd2"}'
# decoded_response = json.loads(response_json)
# print(decoded_response['message'])