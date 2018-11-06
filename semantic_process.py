# setup modules
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from google.cloud.speech import enums
from google.cloud.speech import types
from google.cloud.speech import SpeechClient

import requests
import os
import apiai
import json
import datetime

print ("SYSTEM: listener initialized")

# setup env variable - Google Auth
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"put_file_path_here"
print ("SYSTEM: os.environ.cretentials initialized")

updater = Updater(
    token='put_credential_hash_here')  # provide Telegram Bot Token here
dispatcher = updater.dispatcher
print ("SYSTEM: API token initialized")

# command processing
def startCommand(bot, update):
    bot.send_message(chat_id=update.message.chat_id,
                     text="Tell me, what you'd like to find? You can use either text or audio messages.")

# get command
def complexMessage(bot, update):

    print (f"\n\n---------------------------\nMAIN: request received at {datetime.datetime.now()}")
    print ("MAIN: trying to get audio message")
    request_audio = update.message.voice  # get message data / voice type

    if (request_audio):
        file_info = bot.get_file(request_audio.file_id)
        telegram_response = requests.get(file_info.file_path)

        if telegram_response:
            print("MAIN: audio message recieved")
            audio_content = telegram_response.content

        else:
            print ("MAIN: FATAL ERROR: error getting audio message from server")            
            exit

        # Call audio recognition module
        print("MAIN: call Google Voice Recognition")
        # using link to process voice file via Google (client library)
        response_text = VoiceRecognition(audio_content)
        
        if (response_text):
            print(f"MAIN: recognized voice phrase: {response_text}")
        else:
            response_text = "NDVR"

    else:
        print ("MAIN: no audio detected, trying to get text")
        response_text = update.message.text     # get message data / text type
        if not (response_text):            
            response_text = "NDTR"
            print ("MAIN: no text detected, sending NDTR code")

    # MAIN Process recognized command
    if (response_text == ("NDVR" or "NDTR")):       # trying to see if there are supported types commands
        bot.send_message(chat_id=update.message.chat_id, text='Command not recognized, please try again')

    else:
        print("MAIN: got response from VoiceRecognition, processing to DialogFlow")

        # call GoogleCloud DialogFlow
        df_response = DialogFlowRequest(response_text)

        print(f"MAIN: response from DialogFlow: {df_response['result']['action']}")
        print("MAIN: got response from DialogFlow, trying to get location from request")

        if (df_response != "NDDF"):

            location_msg = GetLocationFromRequest(df_response)

            if ( location_msg in ['NDD', 'NLD', 'FarmExpNoLocation'] ):
                bot.send_message(chat_id=update.message.chat_id, text="Location is not recognized, please try again.") 

            elif ( location_msg == 'NonFarmExp' ): 
                bot.send_message(chat_id=update.message.chat_id, text="Incorrect category. Please try again.")        
            
            else: 
                bot.send_message(chat_id=update.message.chat_id, text="Looking for best options in region: " + location_msg )                
                searchResult = GetLocationSearchResults (location_msg)
                print (f"MAIN: search results output: {searchResult['data']}\n")

                if (searchResult['data'] != "no_results"):

                    print(f"MAIN: Printing search results:\n{searchResult['data']}")
                    bot.send_message(chat_id=update.message.chat_id, text="Location list:\n")

                    for i in ( searchResult['data'] ):
                        qtext = i['title'] + "\nBook a visit: " + i['url'] + "\n\n"
                        bot.send_message(chat_id=update.message.chat_id, text=qtext)
                else:
                    bot.send_message(chat_id=update.message.chat_id, text="Sorry, no locations found in this region. Please try another request.")           

        else:
            bot.send_message(chat_id=update.message.chat_id, text='Sorry, can not recognize your request. please try agait')

    print("\nMAIN: end of request processing, standby...\n---------------------------")

# GoogleCloud recognition
def VoiceRecognition(b_voice_data):
    
    print("VR: initialized")

    try:
        client = SpeechClient()
        print("VR: preparing recognition request")

        audio = types.RecognitionAudio(content=b_voice_data)
        config = types.RecognitionConfig(
            # setup default Telegram format
            encoding=enums.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=16000,
            language_code='en-US',
            max_alternatives=0)

        # Recognize speech content
        print("VR: call for Google Speech API")

        try:
            response = client.recognize(config, audio)
            print("VR: GCS API call finished")
            print (response)

            if (response.results):
                for result in response.results:
                    rec_voice = result.alternatives[0].transcript
                    return rec_voice
            else:
                print("VR: GCS API returned NULL")
                rec_voice = "NDVR"
                return rec_voice

        except Exception as apiClientExpt:
            print("VR: FATAL ERROR: unhandled exception when calling recognize API")
            print (apiClientExpt)

            return False
   
    except Exception as speechClientExpt:
        print ("VR: FATAL ERROR: unhandled exception when initializing SpeechClient")
        print (speechClientExpt)

        return False

# DialogFlow API logic processing (recognized data parsing)
def DialogFlowRequest( df_command ):

    print("DF: initialized")

    # API Dialogflow
    request = apiai.ApiAI('put_api_here').text_request()
    # request language
    request.lang = 'en'
    # training session id
    request.session_id = 'FarmGuestsBot'
    # send request
    request.query = df_command

    print("DF: call for Google DialogFlow API")
    df_response = json.loads(request.getresponse(
    ).read().decode('utf-8'))          # read request
    print("DF: GDF API call finished")

    if (df_response):        
        print(f"DF: DialogFlow output: \n{df_response}")
        
        return df_response

    else:
        print("DF: FATAL ERROR: DialogFlow API returned NULL")
        df_response = "NDDF"
        
        return df_response  # response from DF in JSON


# Parse location from request
def GetLocationFromRequest ( df_response ):

    print ( "GL: initialized" )

    if ( df_response ):

        print("GL: parsing DF response")
        
        if ( df_response['result']['action'] not in ['unknown.action','','input.unknown'] ):
            print( f"GL: speech output: {df_response['result']['fulfillment']['speech']}" )

            if ( df_response['result']['fulfillment']['speech'] != "NoLocation"):
                df_location = df_response['result']['fulfillment']['speech']
            else:
                df_location = "NLD"
        
        else:
            print(f"GL: FATAL ERROR: unsupported DialogFlow output: {df_response['result']['action']}")
            df_location = "NDD"

        return df_location

    else:
        print("GL: FATAL ERROR: possible call with NULL value")
        df_location = "NDD"
        return df_location


# Send Location to SearchEngine
def GetLocationSearchResults ( sLocation ):
    
    print("SearchEngine: initialized")
    queryLink = "search_engine_api_here" + sLocation

    print(f"SearchEngine: Sending search query: {queryLink}")
    response = requests.get(queryLink)
    
    print("SearchEngine: query sent, parsing results:")
    responseJson = response.json()
    print(responseJson)

    return responseJson


# Telegram API handler below
# handler
start_command_handler = CommandHandler('start', startCommand)
complex_message_handler = MessageHandler(Filters.voice | Filters.text, complexMessage)
print("SYSTEM: all handlers active")

# dispatcher handler
dispatcher.add_handler(start_command_handler)
dispatcher.add_handler(complex_message_handler)
print("SYSTEM: all dispatchers active")

# updale lookup
updater.start_polling(clean=True)
print("SYSTEM: all updaters active")
