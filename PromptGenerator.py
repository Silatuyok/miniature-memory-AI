import asyncio
import threading
import time
import datetime


class PromptGenerator:
    def __init__(self, core_personality, user_info, context_window_size, focus_template=None, update_interval=300):
        self.core_personality = core_personality
        self.user_info = user_info
        self.context_window_size = context_window_size
        self.focus_template = focus_template or self.default_focus_template()
        self.deck = {}
        self.focus = {}
        self.focus = {module_details[0]: Module(*module_details) 
                      for module_details in self.focus_template.values()}
        self.update_interval = update_interval
        self.stop_event = asyncio.Event()
        self.updater_task = None  # Initialize as None

    async def __aenter__(self):
        await self.initialize_deck()
        self.updater_task = asyncio.create_task(self.background_updater())  # Create task here
        return self

  
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        self.updater_task.cancel()

    async def initialize_deck(self):
    # properly await coroutine calls for preparation
        preparation_tasks = [module.prepare_data() for module in self.focus.values()]
        await asyncio.gather(*preparation_tasks)
        for module_name, module_instance in self.focus.items():
            self.deck[module_name] = await module_instance.generate_card()
        
    async def background_updater(self):
        try:
            while not self.stop_event.is_set():
                await self.update_deck()
                await asyncio.sleep(self.update_interval)
        except asyncio.CancelledError:
            pass  # Allow clean exit on cancellation
        
    def default_focus_template(self):
        # Returns default focus template
        async def text_data_fetcher():
            return "This is some static text."

        def text_data_processor(data):
            return data, len(data.split()), None

        # Data fetcher and processor for time module
        async def time_data_fetcher():
            return datetime.datetime.now()

        def time_data_processor(data):
            return data.strftime("%Y-%m-%d %H:%M:%S"), len(data.strftime("%Y-%m-%d %H:%M:%S").split()), None
        
        focus_template = {
            "text_module": ("text", text_data_fetcher, text_data_processor, 300),
            "time_module": ("time", time_data_fetcher, time_data_processor, 300),
        }
        
        return focus_template
        
    async def generate_prompt(self):
        prompt = f"{self.core_personality} {self.user_info} "
        used_tokens = len(prompt.split())
        prompt_parts = [
            card_content
            for module_name, (card_content, card_tokens, _) in self.deck.items()
            if (used_tokens + card_tokens) <= self.context_window_size
        ]

        # Calculate total tokens used in the generated parts
        total_tokens_used = sum(len(part.split()) for part in prompt_parts)
        used_tokens += total_tokens_used

        prompt += "\n".join(prompt_parts)
        chat_history = self.generate_chat(used_tokens)
        prompt += chat_history
        return prompt

    def generate_chat(self, used_tokens):
        remaining_tokens = self.context_window_size - used_tokens
        chat = f" [LOG with {remaining_tokens} tokens]"
        # The actual log generation mechanism will use remaining_tokens to determine what to include
        return chat
    
    @async_sync
    async def update_deck(self):
        for module_name in self.focus:  # Iterate over the focus dictionary
            module_instance = self.focus[module_name]
            try:
                self.deck[module_name] = await module_instance.generate_card()  # Generate card from module instance
            except Exception as e:
                print(f"Error updating module {module_name}: {e}")
                continue
    
# Configure your modules here and provide proper data retrieval and processing functions


class Module:
    def __init__(self, name, data_fetcher, data_processor, update_threshold):
        self.data_fetcher = data_fetcher
        self.data_processor = data_processor
        self.update_threshold = update_threshold
        self.name = name

    # data_fetcher and data_processor are functions that are called to retrieve and process data.
    # given that each module is inteded to pull data from different sources, it makes sense to
    # define these functions as parameters of the Module class, so that each instance can have
    # its own data retrieval and processing functions.
    
    #  - data_fetcher: a function that returns the raw data, be it from a database, API, or other source.
    #  this function should take no parameters and return the raw data.
    
    #  - data_processor: a function that processes the raw data and returns the processed data, either
    #  by selecting elements from the raw data such as a JSON object, or by performing some other operation.
    #  this may require sophisticated reasoning, such as the use of another AI model. The data processor
    #  should take the raw data and the module's token budget as parameters, and return a tuple of the
    #  processed data, the number of tokens used, and the timestamp of the data.

    async def prepare_data(self):
        self.data = await self.data_fetcher()
        self.processed_data = self.data_processor(self.data)

    async def generate_card(self):
        if not hasattr(self, 'processed_data'):
            await self.prepare_data()
        return self.processed_data


async def main():
    core_personality = """Your primary role is to act as an experienced planner..."""  # truncated for brevity
    user_info = "UserPrefs: ..."
    context_window_size = 2048  # Example window size

    prompt_generator = PromptGenerator(core_personality, user_info, context_window_size)
    async with prompt_generator:
        full_prompt = await prompt_generator.generate_prompt()
    print(full_prompt)

# Run the main coroutine
asyncio.run(main())
