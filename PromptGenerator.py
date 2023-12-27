import asyncio
import datetime


class PromptGenerator:
    """
    A class used to generate prompts based on a given focus template.

    Attributes:
        core_personality: The core personality of the prompt generator.
        user_info: Information about the user.
        context_window_size: The size of the context window.
        focus_template: A template for the focus of the prompt generator.
        update_interval: The interval at which the prompt generator updates.
    """
    def __init__(self, core_personality, user_info, context_window_size, focus_template=None, update_interval=300):
        """
        Initialize the PromptGenerator with the given parameters.

        :param core_personality: The core personality of the prompt generator.
        :param user_info: Information about the user.
        :param context_window_size: The size of the context window.
        :param focus_template: A template for the focus of the prompt generator. Defaults to None.
        :param update_interval: The interval at which the prompt generator updates. Defaults to 300.
        """
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
        """
        Asynchronously enter the context of the PromptGenerator.

        This method initializes the deck and starts the background updater task.
        """
        await self.initialize_deck()
        self.updater_task = asyncio.create_task(self.background_updater())  # Create task here
        return self

  
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Asynchronously exit the context of the PromptGenerator.

        This method sets the stop event and cancels the updater task.
        """
        self.stop_event.set()
        self.updater_task.cancel()

    async def initialize_deck(self):
        """
        Asynchronously initialize the deck.

        This method prepares data for each module in the focus and generates a card for each module.
        The cards are stored in the deck attribute.
        """
    # properly await coroutine calls for preparation
        preparation_tasks = [module.prepare_data() for module in self.focus.values()]
        await asyncio.gather(*preparation_tasks)
        for module_name, module_instance in self.focus.items():
            self.deck[module_name] = await module_instance.generate_card()
        
    async def background_updater(self):
        """
        Asynchronously update the deck at regular intervals.

        This method runs in a loop until a stop event is set, updating the deck and then sleeping for a specified interval.
        If the task is cancelled, it catches the CancelledError and exits cleanly.
        """
        try:
            while not self.stop_event.is_set():
                await self.update_deck()
                await asyncio.sleep(self.update_interval)
        except asyncio.CancelledError:
            pass  # Allow clean exit on cancellation
        
    def default_focus_template(self):
        """
        Returns the default focus template.

        This method defines data fetcher and processor functions for the text and time modules and returns a dictionary
        with these functions as values and the module names as keys. This is just a trivial example of how to define a focus template.
        """
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
        """
        Asynchronously generate a prompt by combining the core personality, user info, and the generated parts provided by the modules.
        
        Relies on update_deck to keep the data cards up-to-date within their respective tolerances.

        Returns:
            str: The generated prompt to be provided to the LLM.    
        """
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
    
    async def update_deck(self):
        """
        Asynchronously update the content of each module's 'card' in the deck.

        Iterates over each module present in the focus and attempts to generate a new 'card'
        containing the latest data from its respective source. If an update is successful,
        it replaces the existing 'card' in the deck; if not, it prints an error message and moves 
        on to the next module.

        This method is intended to be called periodically in the background by background_updater()
        to ensure that the prompt remains up-to-date with the latest module data.

        Note:
            If an exception occurs during the update of a module, the error is logged, and the 
            update process continues with the next module. This design decision implies that a 
            single failing module does not halt the updates of others.

        Exceptions:
            An exception within a module's generate_card method will be caught and a message will 
            be printed with the module's name and the error. The specific handling of the exception
            depends on the implementation of the module's data_fetching and processing procedures.

        Usage:
            await update_deck()  # update_deck is a coroutine and must be awaited.
        """
        for module_name in self.focus:  # Iterate over the focus dictionary
            module_instance = self.focus[module_name]
            try:
                self.deck[module_name] = await module_instance.generate_card()  # Generate card from module instance
            except Exception as e:
                print(f"Error updating module {module_name}: {e}")
                continue
    
# Configure your modules here and provide proper data retrieval and processing functions


class Module:
    """
    A class used to represent a module. A module is a component of the focus of the prompt generator.
    Instances of this class should be defined in the focus template so they can be cleanly discarded and recreated when the focus template is changed as they can hold substantial amounts of data; 
    however, since their behavior usually amounts to an API call and some simple string processing, they can be defined more concretely in the code for reusability.

    :param name: str, The name of the module.
    
    :param update_threshold: int, The minimum time interval between two updates of the module.
    
    Data fetcher and processor are functions that are used to fetch and process the data for the module. These should be asynchronous functions.
    
    :param data_fetcher: Callable, A function that returns the raw data from a database, API, or other source.
    
    :param data_processor: Callable, A function that processes the raw data and returns the processed data.
    
        Returns:
            (processed_data, tokens_used, timestamp or None)
    
        Raw data should be processed to a string that can be directly used in the prompt.
        This processed data must adhere to the following format:
            - The processed data must be a string. If the data is not a string, it must be converted to a string.
            - The processed data must be within the modules assigned budget. The budget is the number of tokens that the module can use in the prompt.
            - It SHOULD attempt to truncate the data neatly, discarding incomplete sections of the data. For example, if the data is a schedule, it should discard incomplete events. 
            - Try to load as much data as possible within the budget, and determine the actual budget used. This is to allow surpluses to be allocated to the chat history.
    """
    def __init__(self, name, data_fetcher, data_processor, update_threshold):
        self.data_fetcher = data_fetcher
        self.data_processor = data_processor
        self.update_threshold = update_threshold
        self.name = name

    async def prepare_data(self):
        """
        Fetch and process the data asynchronously.

        This method first calls the data_fetcher function to fetch the raw data.
        Then it calls the data_processor function to process the raw data.
        The processed data is stored in the instance variable 'processed_data'.
        """
        self.data = await self.data_fetcher()
        self.processed_data = self.data_processor(self.data)

    async def generate_card(self):
        """
        Generate a card with the processed data.

        If the processed data is not available, it first calls the prepare_data method to prepare the data.
        Then it returns the processed data.

        :return: The processed data.
        """
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

# Generate Docstring for how to define a module's data_fetcher and data_processor, how to define a focus template, and asynch requirements of PromptGenerator. include signatures and examples.

# Run the main coroutine
asyncio.run(main())
